# Changes in this fork

This fork was patched with the help of Claude (Anthropic), working
interactively against a real Blackstar ID:15 TVP over USB on Linux.
Everything below was verified either against that hardware directly,
or (where noted) with a simulated USB device, since some changes
couldn't be safely tested live (e.g. destructive preset writes were
tested on spare preset slots and restored afterwards).

## Bug fixes

- `blackstarid.py`: `set_control` compared a control name with `is`
  instead of `==` (`if control is 'delay_time':`). String identity
  comparison on non-interned strings is unreliable.
- `blackstarid.py`: `BlackstarIDAmpPreset.from_file()` built the
  preset object but never returned it, so it always returned `None`.
- `blackstarid.py`: the tuner note lookup indexed
  `tuner_note[packet[1]]`, off by one against the documented protocol
  (note `E` is coded as `01`, not `00`). Also didn't handle
  `packet[1] == 0` ("no note detected").
- `outsider.py`: `self.preset_settings = [None] * 128` is one short -
  presets are numbered 1..128 and indexed directly by preset number,
  so preset 128 raised `IndexError` and crashed the amp-watcher
  thread the moment that preset was selected.
- `blackstarid.py`: `get_all_preset_names()` fired all 128 name
  requests back to back with no pacing. In testing this overflowed
  the amp's reply queue and only ~17-25 of 128 names ever came back.
  Requests are now paced with a small delay between them.

## New features

- **Save preset**: `BlackstarIDAmp.save_preset_settings()` plus a
  "Save" button in the GUI, writing the amp's current live control
  values (and optionally a new name) to the selected preset slot.
- **Reset preset**: a "Reset" button writes a neutral/blank set of
  values (`DEFAULT_PRESET_SETTINGS`) to a preset slot.
- **Backup / Restore all presets**: `BlackstarIDAmp.read_all_presets()`
  reads the name and full settings of all 128 presets; new "Backup
  All..." / "Restore All..." buttons export/import them to/from a
  JSON file on disk. Restoring asks for confirmation since it
  overwrites the amp's presets and can't be undone.
- **Upload a preset from a file**: `BlackstarIDAmpPreset.to_settings_dict()`
  bridges a preset parsed via `from_file()` (Insider's XML export
  format) or from a JSON backup into the format `save_preset_settings()`
  expects.
- **Graceful disconnect handling**: reading or writing to the amp now
  raises a distinct `AmpDisconnectedError` when the USB device
  actually goes away (as opposed to a normal read timeout, which is
  expected and silent). The GUI catches this, stops the amp-watcher
  thread, resets its state, and tells the user, instead of leaving an
  uncaught exception to potentially wedge the app.
- The tuner display (note, meter, flat/sharp indicator) is wired up in
  the GUI. On the ID:15 TVP we tested, no tuner packets were ever
  observed (holding the TAP button did not trigger tuner mode over
  USB), so this may only be exercised on ID amps that do expose it.
- 10 starting-point genre presets (jazz, blues, classic rock, hard
  rock, metal, djent, funk, ambient, country, acoustic-style) - see the
  amp's presets 26-35 if you used the same slots we proposed. These are
  reasonable defaults, not "the correct tone" for anything - guitar,
  pickups and taste vary.

## Not implemented (see README for why)

- Noise gate control.
- Effects loop on/off, super-wide stereo on/off (not applicable to
  mono, no-FX-loop combos like the ID:15 TVP).

## Known rough edges not addressed here

- `AmpControlWatcher` still polls in a loop rather than using a more
  idiomatic Qt/event-driven read strategy (a small sleep was added to
  stop it spinning at 100% CPU, but it's still a polling loop).
- No automated test suite. Everything here was verified with
  print-driven manual scripts and (for destructive operations) real
  hardware, restored afterwards.
