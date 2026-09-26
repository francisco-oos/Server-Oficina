from app.services.sync_topology import (
    SyncFolderPlan,
    build_device_config,
    build_folder_config,
    lan_only_options_patch,
    topology_summary,
)


def test_lan_only_options_disable_internet_paths():
    patch = lan_only_options_patch()
    assert patch["globalAnnounceEnabled"] is False
    assert patch["relaysEnabled"] is False
    assert patch["natEnabled"] is False
    assert patch["localAnnounceEnabled"] is True


def test_folder_plan_is_send_receive_and_keeps_conflicts():
    payload = build_folder_config(
        SyncFolderPlan(
            folder_id="material",
            label="Control de Material",
            path="/srv/server-oficina/files/Control_Material",
            device_ids=("PC-B", "PC-A", "PC-A"),
        )
    )
    assert payload["type"] == "sendreceive"
    assert payload["fsWatcherEnabled"] is True
    assert payload["maxConflicts"] == 25
    assert payload["versioning"]["type"] == "staggered"
    assert payload["devices"] == [{"deviceID": "PC-A"}, {"deviceID": "PC-B"}]


def test_device_is_not_introducer_or_auto_acceptor():
    payload = build_device_config("AAAA-BBBB", name="Material 01")
    assert payload["deviceID"] == "AAAA-BBBB"
    assert payload["autoAcceptFolders"] is False
    assert payload["introducer"] is False


def test_topology_is_star_and_offline_capable():
    summary = topology_summary(peer_count=24, share_count=5)
    assert summary["mode"] == "STAR"
    assert summary["hub"] == "server-oficina"
    assert summary["peer_count"] == 24
    assert summary["internet_required"] is False
