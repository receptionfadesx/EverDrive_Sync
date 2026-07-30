"""Named profiles — one saved set of paths/options per system or SD card.

The config file holds every profile plus which one is active::

    {
      "ActiveProfile": "Game Boy",
      "Profiles": {
        "Game Boy": {"Source": "...", "Dest": "...", ..., "Options": {...}},
        "N64":      {"Source": "...", "Dest": "...", ..., "Options": {...}}
      }
    }

Configs written by older versions are a single flat profile; :func:`normalize_config`
migrates those into ``Profiles["Default"]`` on read, so upgrading keeps the paths
the user already had.
"""
import json
import os

DEFAULT_PROFILE_NAME = "Default"

# Path/file entries that make up a profile (each also has an "Options" dict)
PROFILE_PATH_KEYS = ("Source", "Hacks", "GbcSysPayload", "Dest", "DatFile")


def blank_profile():
    """Return an empty profile with every key present."""
    profile = {key: "" for key in PROFILE_PATH_KEYS}
    profile["Options"] = {}
    return profile


def coerce_profile(data):
    """Return a well-formed profile from arbitrary saved data (hand-edited files)."""
    profile = blank_profile()
    if not isinstance(data, dict):
        return profile
    for key in PROFILE_PATH_KEYS:
        value = data.get(key)
        if isinstance(value, str):
            profile[key] = value
    options = data.get("Options")
    if isinstance(options, dict):
        profile["Options"] = {
            k: bool(v) for k, v in options.items() if isinstance(k, str)
        }
    return profile


def normalize_config(data):
    """Upgrade any saved config to the profile format.

    Always returns ``{"ActiveProfile": name, "Profiles": {...}}`` with at least one
    profile and an ``ActiveProfile`` that exists in it.
    """
    if not isinstance(data, dict):
        data = {}
    profiles = {}
    raw = data.get("Profiles")
    if isinstance(raw, dict):
        for name, profile in raw.items():
            if isinstance(name, str) and name.strip():
                profiles[name.strip()] = coerce_profile(profile)
    if not profiles:
        # Legacy flat config (or no config at all) becomes the one profile.
        profiles[DEFAULT_PROFILE_NAME] = coerce_profile(data)
    active = data.get("ActiveProfile")
    if not isinstance(active, str) or active not in profiles:
        active = next(iter(profiles))
    return {"ActiveProfile": active, "Profiles": profiles}


def load_config_file(path):
    """Read *path* and return a normalized config; never raises."""
    data = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            data = {}
    return normalize_config(data)


def save_config_file(path, config):
    """Write *config* to *path*. Returns True on success, False if unwritable."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return True
    except OSError:
        return False


def profile_names(config):
    """Profile names in saved order."""
    return list(config.get("Profiles", {}))


def get_profile(config, name=None):
    """Return the named profile, or the active one when *name* is None."""
    profiles = config.get("Profiles", {})
    if name is None:
        name = config.get("ActiveProfile")
    return profiles.get(name)


def unique_profile_name(config, base):
    """Return *base*, or ``base (2)``, ``base (3)``... if that name is taken."""
    existing = {n.lower() for n in profile_names(config)}
    if base.lower() not in existing:
        return base
    for n in range(2, 1000):
        candidate = "{} ({})".format(base, n)
        if candidate.lower() not in existing:
            return candidate
    return base


def rename_profile(config, old, new):
    """Rename a profile in place, preserving order. Returns True if renamed."""
    profiles = config.get("Profiles", {})
    if old not in profiles or not new or (new != old and new in profiles):
        return False
    config["Profiles"] = {
        (new if name == old else name): profile
        for name, profile in profiles.items()
    }
    if config.get("ActiveProfile") == old:
        config["ActiveProfile"] = new
    return True
