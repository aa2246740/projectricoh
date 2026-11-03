"""用真实文件读写和独立挂载模型核对导入阶段。"""

import os
from pathlib import Path

import pytest

from gxr_studio import audit
from gxr_studio.cards import coverage, discovery, importer
from gxr_studio.library.store import Library

from review_support import attached, card_at, digest, options, record


class ReadingFile:
    def __init__(self, file, action):
        self.file, self.action = file, action

    def __enter__(self):
        self.file.__enter__()
        return self

    def __exit__(self, *args):
        return self.file.__exit__(*args)

    def fileno(self):
        return self.file.fileno()

    def read(self, amount=-1):
        block = self.file.read(amount)
        if block:
            self.action()
        return block


class ReadingCard(discovery.CardReader):
    def __init__(self, action):
        self.action = action

    def open_rb(self, path):
        return ReadingFile(super().open_rb(path), self.action)


@pytest.mark.parametrize("kind", ["jpg", "avi"])
@pytest.mark.parametrize("phase", ["before_first_read", "during_read", "after_stage", "after_item", "final_check"])
@pytest.mark.parametrize("change", ["fsid", "device", "detached", "root_inode"])
def test_session_changes(tmp_path, monkeypatch, kind, phase, change):
    card = card_at(tmp_path, (kind,))
    probe, registry, mount, identity = attached(card)
    library = Library(tmp_path / "library").open()
    original = next((card.root / "DCIM/100RICOH").iterdir()).read_bytes()
    prior = card.root.with_name("CARD-prior")
    fired = []
    audit.protect(card.root)

    def change_mount(*args):
        if fired:
            return
        fired.append(phase)
        if change == "fsid":
            probe.number += 1
        elif change == "device":
            probe.device = "local-model-b"
        elif change == "detached":
            probe.available = False
        else:
            audit.unprotect(card.root)
            card.root.rename(prior)
            (card.root / "DCIM/100RICOH").mkdir(parents=True)
            audit.protect(card.root)
            audit.protect(prior)

    opts = options()
    reader = discovery.CardReader()
    if phase == "before_first_read":
        original_scan = importer.scan_card
        def scan(*args, **kwargs):
            value = original_scan(*args, **kwargs)
            change_mount()
            return value
        monkeypatch.setattr(importer, "scan_card", scan)
    elif phase == "during_read":
        reader = ReadingCard(change_mount)
    elif phase == "after_stage":
        opts.before_verify = change_mount
    elif phase == "after_item":
        if kind == "jpg":
            opts.after_shot = change_mount
        else:
            actual = importer.videos_mod.import_video
            def video(*args, **kwargs):
                actual(*args, **kwargs)
                change_mount()
            monkeypatch.setattr(importer.videos_mod, "import_video", video)
    else:
        actual = coverage.photo_coverage
        def final_check(*args, **kwargs):
            value = actual(*args, **kwargs)
            change_mount()
            return value
        monkeypatch.setattr(coverage, "photo_coverage", final_check)
    try:
        with audit.AuditRecorder() as writes:
            result = importer.run_import(library, card, opts, reader=reader, ident=identity)
        count = library.count() if kind == "jpg" else library.video_count()
        present = [p for p in library.root.rglob("*." + kind.upper())]
        record("session_changes", {"kind": kind, "phase": phase, "change": change,
               "progress": result.to_dict(), "count": count,
               "source_present_in_library": any(p.read_bytes() == original for p in present),
               "card_write_events": [vars(w) for w in writes.writes_under(card.root) if w.op != "os.rename"]})
        assert fired and result.state == "interrupted"
        assert not (result.coverage or {}).get("all_imported", False)
        assert not list(library.staging_dir.iterdir())
        assert count == (1 if phase in ("after_item", "final_check") else 0)
        if count:
            assert any(p.read_bytes() == original for p in present)
        with pytest.raises(Exception) as error:
            registry.resolve(mount.session_id)
        assert getattr(error.value, "status", None) == 404
    finally:
        audit.unprotect(card.root)
        audit.unprotect(prior)
        library.close()


@pytest.mark.parametrize("kind", ["jpg", "avi"])
@pytest.mark.parametrize("change", ["in_place", "new_inode"])
def test_file_proof_checks_current_state(tmp_path, monkeypatch, kind, change):
    card = card_at(tmp_path, (kind,))
    source = next((card.root / "DCIM/100RICOH").iterdir())
    library = Library(tmp_path / "library").open()
    probe, registry, mount, identity = attached(card)
    audit.protect(card.root)
    try:
        assert importer.run_import(library, card, options(), ident=identity).coverage["all_imported"]
        original = source.read_bytes()
        state = source.stat()
        changed = bytes(byte ^ 74 for byte in original)
        fired = []

        def replace_source(*args):
            if fired:
                return
            fired.append(True)
            audit.unprotect(card.root)
            try:
                if change == "in_place":
                    source.write_bytes(changed)
                else:
                    other = source.with_name("replacement.bin")
                    other.write_bytes(changed)
                    os.replace(other, source)
                os.utime(source, ns=(state.st_atime_ns, state.st_mtime_ns))
            finally:
                audit.protect(card.root)

        opts = options()
        if kind == "jpg":
            opts.after_shot = replace_source
        else:
            actual = importer.videos_mod.import_video
            def video(*args, **kwargs):
                actual(*args, **kwargs)
                replace_source()
            monkeypatch.setattr(importer.videos_mod, "import_video", video)
        result = importer.run_import(library, card, opts, ident=identity)
        record("file_proof_checks_current_state", {"kind": kind, "change": change, "progress": result.to_dict(),
               "new_sha_in_library": library.sha_in_library(digest(changed), len(changed))})
        assert fired and mount.still_valid()
        assert result.state == "done" and not result.coverage["all_imported"]
        assert result.coverage["uncovered"] == [source.relative_to(card.root).as_posix()]
    finally:
        audit.unprotect(card.root)
        library.close()
