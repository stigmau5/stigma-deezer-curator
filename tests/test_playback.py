import tempfile
import unittest
from pathlib import Path

from audio_division.operation_runner import load_operation_history
from audio_division.playback import (
    first_playlist,
    playback_summary,
    playback_target,
    player_provider_from_settings,
    prepare_playback_command,
    run_playback_action,
)
from audio_division.settings import default_settings


class FakeProcess:
    pid = 1234


class PlaybackTests(unittest.TestCase):
    def test_player_provider_from_settings(self):
        settings = {"playback": {"provider": "vlc", "player_path": "/usr/bin/vlc", "player_args": "--one-instance"}}
        provider = player_provider_from_settings(settings)

        self.assertEqual(provider.id, "vlc")
        self.assertEqual(provider.command(Path("/music/album")), ["/usr/bin/vlc", "--one-instance", "/music/album"])

    def test_first_playlist_prefers_m3u8(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp)
            (album / "album.m3u").write_text("track.flac")
            (album / "album.m3u8").write_text("track.flac")

            self.assertEqual(first_playlist(album).name, "album.m3u8")

    def test_play_album_prefers_playlist_then_album_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp)
            playlist = album / "release.m3u8"
            playlist.write_text("track.flac")

            target, message = playback_target("play_album", album)

        self.assertEqual(message, "ok")
        self.assertEqual(target.path, playlist)
        self.assertEqual(target.kind, "playlist")

    def test_play_album_falls_back_to_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp)

            target, message = playback_target("play_album", album)

        self.assertEqual(message, "ok")
        self.assertEqual(target.path, album)
        self.assertEqual(target.kind, "album_folder")

    def test_play_playlist_requires_playlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            target, message = playback_target("play_playlist", Path(tmp))

        self.assertIsNone(target)
        self.assertIn("No playlist", message)

    def test_prepare_playback_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp)
            playlist = album / "release.m3u8"
            playlist.write_text("track.flac")
            settings = {"playback": {"provider": "mpv", "player_path": "/bin/echo", "player_args": "--no-video"}}

            command, message = prepare_playback_command("play_album", album, settings)

        self.assertEqual(message, "ok")
        self.assertEqual(command, ["/bin/echo", "--no-video", str(playlist)])

    def test_run_playback_records_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp) / "Album"
            album.mkdir()
            (album / "playlist.m3u8").write_text("track.flac")
            history_path = Path(tmp) / "operation_history.json"
            settings = {"playback": {"player_path": "/bin/echo"}}

            def runner(command):
                self.assertEqual(command[-1], str(album / "playlist.m3u8"))
                return FakeProcess()

            result = run_playback_action("play_album", album, settings, history_path, runner=runner)
            history = load_operation_history(history_path)

        self.assertEqual(result["result"], "success")
        self.assertEqual(result["operation"], "play_album")
        self.assertEqual(history["history"][0]["operation"], "play_album")

    def test_playback_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp)
            (album / "playlist.m3u8").write_text("track.flac")
            summary = playback_summary({"archive_path": str(album)})

        self.assertTrue(summary["album_available"])
        self.assertTrue(summary["playlist_available"])
        self.assertEqual(summary["album_source"], "album_playlist")

    def test_settings_defaults_include_playback(self):
        settings = default_settings()

        self.assertEqual(settings["playback"]["provider"], "mpv")
        self.assertEqual(settings["playback"]["player_path"], "mpv")


if __name__ == "__main__":
    unittest.main()
