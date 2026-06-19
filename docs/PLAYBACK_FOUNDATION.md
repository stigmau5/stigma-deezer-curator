# Playback Foundation

Playback is an album-workspace action. It is intentionally an orchestration layer around an external player, not a custom audio engine.

## Philosophy

- Filesystem evidence remains the source of truth.
- Playback is always user initiated.
- The Hub does not download, transcode, tag, or rewrite audio.
- The Hub launches a configured external player with an album target.

## Player Provider

`audio_division.playback.PlayerProvider` represents the selected external player.

Current settings:

- `playback.provider`: provider name, default `mpv`
- `playback.player_path`: executable path, default `mpv`
- `playback.player_args`: optional command arguments

The provider model is intentionally small so future providers such as `vlc` can be added without changing album workspace logic.

## Target Selection

`Play Album` resolves targets in this order:

1. album playlist, preferring `.m3u8` before `.m3u`
2. album folder

`Play Playlist` requires an existing `.m3u8` or `.m3u` playlist and reports a clear failure if none exists.

## History

Playback launches are recorded in `operation_history.json` through the existing operation history writer. This keeps Recent Operations useful without introducing a new database or playback state file.

## Future Work

Possible future extensions:

- explicit mpv/vlc provider presets
- stop/pause controls delegated to player-specific providers
- playback queue
- playlist inspection before launch

Those should remain external-player integrations. The Hub should not become a custom audio decoding engine.
