"""The bundle check's local-path rule, on a synthetic bundle built on a GitHub runner.

There the builder's home is /Users/runner, upstream files copied into the bundle name
their own /Users/runner/... build paths, and "runner" is also ordinary text in
BioBridge's own code. Only paths from this build may be reported.
"""

import importlib.util
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_app_bundle", REPO / "scripts" / "check_app_bundle.py")
check_app_bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_app_bundle)

HOME = Path("/Users/runner")
CHECKOUT = Path("/Users/runner/work/biobridge/biobridge")


def bundle(tmp_path, files):
    app = tmp_path / "BioBridge.app"
    for rel, data in files.items():
        (app / rel).parent.mkdir(parents=True, exist_ok=True)
        (app / rel).write_bytes(data)
    return app


def test_runner_username_and_upstream_build_paths_are_not_reported(tmp_path):
    app = bundle(tmp_path, {
        "Contents/Resources/app/biobridge/adapters/spliceai/runner.py": b'"""The SpliceAI runner."""\n',
        "Contents/MacOS/BioBridge": b"\x00/Users/runner/work/briefcase-macOS-template/stub.m\x00",
        "Contents/Resources/app_packages/markupsafe/_speedups.cpython-311-darwin.so":
            b"\x00/Users/runner/work/markupsafe/markupsafe/src/_speedups.c\x00",
        "Contents/Resources/app_packages/bin/uv": b"\xcf\xfa\xed\xfe/Users/runner/.cargo/registry/src\x00",
    })
    assert check_app_bundle.local_paths(app, CHECKOUT, HOME) == []


def test_build_checkout_path_is_reported_anywhere(tmp_path):
    app = bundle(tmp_path, {
        "Contents/Resources/app_packages/bin/tool": b"#!/Users/runner/work/biobridge/biobridge/build/python\n",
        "Contents/Resources/app_packages/thirdparty/mod.so": b"\x00/Users/runner/work/biobridge/biobridge/x\x00",
    })
    found = check_app_bundle.local_paths(app, CHECKOUT, HOME)
    assert found == ["embeds the build checkout's path: Contents/Resources/app_packages/bin/tool",
                     "embeds the build checkout's path: Contents/Resources/app_packages/thirdparty/mod.so"]


def test_home_directory_is_reported_in_files_this_build_writes(tmp_path):
    app = bundle(tmp_path, {
        "Contents/Resources/app/biobridge/_build_info.json": b'{"note": "/Users/runner/Library/x"}',
        "Contents/Info.plist": b"<string>/Users/runner/x</string>",
        "Contents/Resources/app_packages/foo-1.0.dist-info/direct_url.json": b'{"url": "file:///Users/runner/x"}',
        "Contents/Resources/app_packages/bin/script": b"#!/Users/runner/.local/bin/python3\n",
    })
    found = check_app_bundle.local_paths(app, CHECKOUT, HOME)
    assert [line.split(": ", 1)[1] for line in found] == [
        "Contents/Info.plist",
        "Contents/Resources/app/biobridge/_build_info.json",
        "Contents/Resources/app_packages/bin/script",
        "Contents/Resources/app_packages/foo-1.0.dist-info/direct_url.json",
    ]
    assert all(line.startswith("embeds the builder's home directory") for line in found)


def test_the_check_does_not_write_into_the_bundle(tmp_path):
    """Importing BioBridge from the bundle must not leave __pycache__ (with local paths) in it."""
    app = bundle(tmp_path, {"Contents/Info.plist": plistlib.dumps({"CFBundleShortVersionString": "0.1.0"})})
    shutil.copytree(REPO / "src" / "biobridge", app / "Contents/Resources/app/biobridge",
                    ignore=shutil.ignore_patterns("__pycache__", "_build_info.json"))
    before = sorted(p.relative_to(app) for p in app.rglob("*"))
    subprocess.run([sys.executable, REPO / "scripts" / "check_app_bundle.py", app], capture_output=True)
    assert sorted(p.relative_to(app) for p in app.rglob("*")) == before


def test_bundle_identifier_is_real_and_matches_the_launcher():
    expected = check_app_bundle.bundle_identifier(REPO / "pyproject.toml")
    assert expected == "io.github.rinatrizvanov.biobridge"
    assert not expected.startswith(check_app_bundle.PLACEHOLDER_PREFIXES)
    launcher = (REPO / "src" / "biobridge" / "launcher.py").read_text()
    assert f'APP_ID = "{expected}"' in launcher


def test_required_license_texts_exist_in_the_source():
    prefix = "Contents/Resources/app/"
    shipped = [rel for rel in check_app_bundle.REQUIRED if "/third_party_licenses/" in rel]
    assert len(shipped) == 5
    for rel in shipped:
        assert (REPO / "src" / rel.removeprefix(prefix)).is_file(), rel


def test_runtime_versions_and_matching_python_license(tmp_path):
    framework = "Contents/Frameworks/Python.framework/Versions/3.13"
    app = bundle(tmp_path, {
        f"{framework}/Resources/Info.plist": plistlib.dumps({"CFBundleVersion": "3.13.16"}),
        f"{framework}/lib/libcrypto.3.dylib": b"\x00OpenSSL 3.5.9 29 Sep 2026\x00",
    })
    assert check_app_bundle.runtime_versions(app) == ("3.13.16", "3.5.9")
    assert (REPO / "src/biobridge/third_party_licenses/python-3.13.16-license.rst").is_file()
