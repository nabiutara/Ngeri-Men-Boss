# Private cloud deployment

The Windows desktop version remains local. This optional deployment adds a private
phone-accessible site, Cloudflare Pages Functions for authenticated job and upload
management, Cloudflare R2 for temporary source clips and retained result/candidate
artifacts, D1 for job state, and a Modal L4 worker for tracking and candidate training.

## Data and model behavior

- Raw video is uploaded directly from the browser to the private R2 bucket in 64 MiB
  multipart chunks with signed, single-part URLs that expire after 24 hours. The GPU
  worker attempts deletion after tracking and pseudo-label extraction, including
  failed jobs. A one-day R2 lifecycle rule cleans up abandoned objects if a worker is
  terminated before its cleanup runs.
- Sparse, confidence-filtered frames and YOLO labels are retained on a private Modal
  Volume. The upload hash deduplicates identical clips.
- Each eligible upload trains a one-epoch candidate from the verified football
  checkpoint using a balanced subset of up to 10,000 retained pseudo-labeled frames.
  A candidate and provenance manifest are saved to R2; the active checkpoint is never
  changed. No reviewed validation score is claimed.
- At least four total retained sample frames and one new usable frame from the current
  upload are needed to create a candidate.
- Cloud use incurs storage and GPU charges. Configure R2 lifecycle rules to abort
  incomplete multipart uploads after one day and remove abandoned `uploads/` objects
  after one day. Completed originals are explicitly deleted by the worker.

Prediction-only training can reinforce teacher errors. Keep candidate-only behavior
until a reviewed, match-separated benchmark establishes that a candidate is better.
The existing checksum-verified football checkpoint remains the inference model.

## 1. Cloudflare setup

1. Create an R2 bucket named `touchline-studio-private` and an S3 API token limited
   to that bucket. Keep its access and secret keys private.
2. Configure bucket CORS to allow `PUT` from the Pages site origin, with the
   `Content-Type` request header, and expose the `ETag` response header. The browser
   needs ETags to complete its multipart upload.
3. Create a D1 database named `touchline-studio` and set its ID in `wrangler.toml`.
   From this directory, run:

   ```sh
   npm install
   npx wrangler d1 execute touchline-studio --remote --file migrations/0001_create_jobs.sql
   ```

4. Create a Cloudflare Access self-hosted application for the Pages domain. Allow
   only your email account. Create a more-specific `/api/internal/*` Bypass policy
   because Modal calls that endpoint with a separate high-entropy shared secret;
   all other UI and API paths remain behind Access. Copy the Access team domain and
   application audience tag into `wrangler.toml`.
5. Create the Pages project with this directory as its project root and `../dist` as
   its build output. Create these Pages secrets (never commit their values):
   `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `MODAL_KEY`, `MODAL_SECRET`, and
   `CALLBACK_SECRET`. Set `CALLBACK_SECRET` to the same random secret used by Modal.
   Set the account, bucket, Access, D1 and Modal URL values in `wrangler.toml`.

## 2. Modal setup

Install the deployment dependencies and authenticate in the Modal CLI:

```sh
python -m pip install -r cloud/requirements.txt
modal setup
```

Create two private Modal Secrets:

- `touchline-r2`: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
  `R2_BUCKET`.
- `touchline-callback`: `TOUCHLINE_CALLBACK_URL` (the HTTPS Pages origin) and
  `TOUCHLINE_CALLBACK_SECRET` (same value as Cloudflare's `CALLBACK_SECRET`).

Create a Modal proxy token for Cloudflare's server-side calls. Deploy from the
project root so the two local source files are packaged into the GPU image:

```sh
modal deploy cloud/modal_app.py
```

Copy the deployed `web-api` HTTPS endpoint into `MODAL_API_URL`. The API requires
Modal Proxy authentication; its key and secret belong only in Cloudflare Pages
secrets, never in browser code.

## 3. Pages deploy and private access

From `cloud/`, run:

```sh
npm run deploy
```

Then enable the Access application and confirm its email allowlist. The API also
verifies the Cloudflare Access JWT against the team signing keys and expected
audience. The internal callback route validates its separate shared secret.
`/api/health` reports `ready: true` only when the required configuration is present.

## 4. Smoke-check before phone use

1. Open the Pages domain while signed in through Access and check `/api/health`.
2. Upload a short, non-sensitive test clip, wait for tracking and candidate status,
   and verify the raw object is removed from `uploads/`.
3. Confirm the saved tracking result is downloadable and the candidate is recorded
   as inactive. A failed candidate-training step must not invalidate tracking.
4. Only then upload match footage from the phone. Video and pseudo-label images leave
   the device and are stored by the selected cloud providers under the policy above.

Deployment is not complete until provider accounts, secrets, Access policy, CORS,
database, and a successful smoke check are configured. Do not expose the local
`server.py` listener to the public internet.
