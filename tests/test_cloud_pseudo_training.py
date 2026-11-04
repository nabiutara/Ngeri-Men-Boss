import json
from pathlib import Path
import sys
import tempfile
import unittest

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from pseudo_training import build_pseudo_samples, write_dataset_config


class PseudoTrainingTests(unittest.TestCase):
    def _video_and_result(self, root, *, repeated=True):
        video = root / "clip.avi"
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 2, (80, 60))
        self.assertTrue(writer.isOpened())
        frames = []
        for index in range(10):
            writer.write(np.full((60, 80, 3), index * 20, np.uint8))
            players = [{"id": 7, "x": .5, "y": .8, "w": .2, "h": .4,
                        "conf": .9, "role": "player"}]
            if index == 0:
                players.append({"id": 8, "x": .25, "y": .7, "w": .1, "h": .2,
                                "conf": .99, "role": "goalkeeper"})
            frames.append({"t": index / 2, "players": players,
                           "camera": {"scene": 0},
                           "ball": {"x": .6, "y": .5, "w": .04, "h": .04,
                                    "conf": .9, "observed": index in (0, 1)}})
        writer.release()
        if not repeated:
            for frame in frames:
                frame["players"][0]["id"] = int(frame["t"] * 2) + 100
                frame["ball"]["observed"] = False
        result = {"schema": "touchline-tracks-v1", "model": "football-best.pt",
                  "class_names": {"0": "ball", "1": "goalkeeper", "2": "player", "3": "referee"},
                  "fps": 2, "frames": frames}
        return video, result

    def test_writes_sparse_confident_pseudolabels_and_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            video, result = self._video_and_result(root)
            samples = root / "samples"
            info = build_pseudo_samples(video, result, samples)
            self.assertEqual(info["sampled_frames"], 5)
            repeated = build_pseudo_samples(video, result, samples)
            self.assertTrue(repeated["duplicate_upload"])
            self.assertEqual(repeated["sampled_frames"], 5)
            sample_dir = Path(info["sample_directory"])
            rows = (sample_dir / "labels" / "00000000.txt").read_text().splitlines()
            self.assertEqual(rows[0], "2 0.50000000 0.60000000 0.20000000 0.40000000")
            self.assertEqual(rows[1], "0 0.60000000 0.50000000 0.04000000 0.04000000")
            self.assertFalse(any(row.startswith("1 ") for row in rows),
                             "Single-frame tracks are excluded from pseudo labels")
            manifest = json.loads((sample_dir / "provenance.json").read_text())
            self.assertEqual(manifest["schema"], "touchline-pseudo-samples-v1")
            self.assertEqual(manifest["source_sha256"], info["source_sha256"])
            self.assertEqual(len(manifest["frames"]), 5)
            self.assertEqual(write_dataset_config(samples, root / "training" / "data.yaml"), 5)
            config = (root / "training" / "data.yaml").read_text()
            self.assertIn("train-images.txt", config)
            self.assertIn("val:", config)
            self.assertIn("2: player", config)
            from ultralytics.data.utils import check_det_dataset
            checked = check_det_dataset(str(root / "training" / "data.yaml"))
            self.assertEqual(checked["names"][2], "player")

    def test_single_frame_tracks_are_not_treated_as_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            video, result = self._video_and_result(root, repeated=False)
            info = build_pseudo_samples(video, result, root / "samples")
            self.assertEqual(info["sampled_frames"], 0)
            self.assertFalse(Path(info["sample_directory"]).exists())

    def test_rejects_class_map_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            video, result = self._video_and_result(root)
            result["class_names"]["0"] = "person"
            with self.assertRaisesRegex(ValueError, "must match"):
                build_pseudo_samples(video, result, root / "samples")

    def test_rejects_changed_class_order(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            video, result = self._video_and_result(root)
            result["class_names"]["0"], result["class_names"]["2"] = "player", "ball"
            with self.assertRaisesRegex(ValueError, "must match"):
                build_pseudo_samples(video, result, root / "samples")

    def test_training_sample_cap_balances_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            samples = root / "samples"
            for source in ("a" * 64, "b" * 64):
                images = samples / source / "images"
                images.mkdir(parents=True)
                for frame in range(3):
                    (images / f"{frame:08d}.jpg").write_bytes(b"image")
            self.assertEqual(write_dataset_config(samples, root / "train" / "data.yaml", max_images=4), 4)
            chosen = (root / "train" / "train-images.txt").read_text().splitlines()
            self.assertEqual(len(chosen), 4)
            self.assertEqual(sum("a" * 64 in path for path in chosen), 2)
            self.assertEqual(sum("b" * 64 in path for path in chosen), 2)


if __name__ == "__main__":
    unittest.main()
