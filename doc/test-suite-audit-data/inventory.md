# Complete collected-family inventory

Generated from the three baseline runs and Python ASTs.

Expanded case evidence was captured in ignored `raw/baseline-1.json.gz`, removed during delivery cleanup.
This inventory remains historical; the documented runner captures new evidence from the current test tree.
`provenance.json` preserves original module hashes; `assertion-candidates.json` lists the supplemental overlap scan.
Numbers below count collected cases, not loop iterations. Source lines are one-based.

## tests/atc/test_block.py

4 cases; 4 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestBlock::test_create_block` | 1 | _xunit_setup_method_fixture_TestBlock |
| `TestBlock::test_slow_down_hands_the_restriction_to_the_threaded_ramp` | 1 | _xunit_setup_method_fixture_TestBlock, monkeypatch |
| `TestBlock::test_slow_down_is_silent_at_or_below_the_restriction` | 1 | _xunit_setup_method_fixture_TestBlock, monkeypatch |
| `TestBlock::test_resume_speed_hands_the_original_speed_to_the_threaded_ramp` | 1 | _xunit_setup_method_fixture_TestBlock, monkeypatch |

## tests/cli/test_ancillary_logging.py

10 cases; 1 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_ancillary_entry_point_initializes_logging` | 10 | class_name, module_name, monkeypatch |

## tests/cli/test_cache.py

2 cases; 2 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_cache_parser_accepts_delete_file_command` | 1 |  |
| `test_interactive_cache_delete_preserves_filename_case` | 1 | monkeypatch |

## tests/cli/test_cache_sync_service.py

38 cases; 13 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_cache_sync_properties_default_to_disabled_and_derived_port` | 1 |  |
| `test_cache_sync_properties_parse_enabled_and_port` | 1 |  |
| `test_cache_sync_property_variants` | 9 | expected, properties |
| `test_invalid_utf8_service_properties_raise` | 2 | properties |
| `test_register_service_encodes_capabilities_and_addresses` | 4 | bare_pytrain, cache_service, enabled, hostname, monkeypatch, port, pytrain_isolation |
| `test_update_service_preserves_existing_properties_and_reregisters` | 2 | bare_pytrain, cache_service, monkeypatch, pytrain_isolation, updates |
| `test_update_service_currently_leaves_serialized_txt_properties_stale` | 1 | bare_pytrain, cache_service, monkeypatch, pytrain_isolation |
| `test_advertisement_transport_failures_propagate` | 3 | bare_pytrain, cache_service, monkeypatch, operation, pytrain_isolation |
| `test_cache_sync_manager_arguments_and_startup_idempotence` | 7 | bare_pytrain, cache_service, capable, has_address, is_server, monkeypatch, pytrain_isolation |
| `test_disabled_cache_sync_does_not_construct_manager` | 1 | bare_pytrain, cache_service, monkeypatch, pytrain_isolation |
| `test_failed_cache_sync_start_is_not_retried` | 1 | bare_pytrain, cache_service, monkeypatch, pytrain_isolation |
| `test_shutdown_cache_preserves_service_and_is_idempotent` | 2 | bare_pytrain, cache_service, capsys, has_manager, monkeypatch, pytrain_isolation |
| `test_shutdown_cache_retains_manager_on_failure_then_retries` | 4 | bare_pytrain, cache_service, capsys, error_type, failures, monkeypatch, pytrain_isolation |

## tests/cli/test_configure.py

12 cases; 12 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_resolve_existing_path_prefers_top_level` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_resolve_existing_path_falls_back_to_cache` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_print_edit_target_reports_cache_file` | 1 | capsys, monkeypatch, tmp_path, tmp_path_factory |
| `test_copy_cache_to_local_keeps_cache_file` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_move_local_to_cache_removes_top_level_file` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_copy_cache_to_local_command_line` | 1 | capsys, monkeypatch, tmp_path, tmp_path_factory |
| `test_copy_cache_to_local_requires_force_to_overwrite` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_interactive_move_local_to_shared_cache` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_interactive_prompt_hides_cache_copy_when_cache_file_missing` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_interactive_prompt_hides_cache_move_when_local_file_missing` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_delete_command_line_removes_selected_accessory` | 1 | capsys, monkeypatch, tmp_path, tmp_path_factory |
| `test_existing_file_prompt_can_delete_before_append` | 1 | monkeypatch, tmp_path, tmp_path_factory |

## tests/cli/test_lcs.py

27 cases; 20 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_parser_defaults_to_a_client_with_no_window_overrides` | 1 |  |
| `test_parser_accepts_each_connection_and_window_option` | 7 | attribute, cmd_line, expected |
| `test_main_returns_zero_and_passes_its_arguments_through` | 1 | monkeypatch |
| `test_main_reads_sys_argv_when_given_nothing` | 1 | monkeypatch |
| `test_main_exits_rather_than_raising_when_the_cli_fails` | 1 | monkeypatch |
| `test_send_opens_the_window_with_the_requested_geometry_and_runs_its_loop` | 1 | monkeypatch |
| `test_send_does_not_wait_for_sync_and_shuts_pytrain_down_afterwards` | 1 | monkeypatch |
| `test_send_builds_no_requests` | 1 |  |
| `test_host_defaults_to_the_portrait_overlay_geometry` | 1 | _patch_runtime, monkeypatch |
| `test_host_supplies_the_surface_the_panel_and_popup_manager_read` | 1 | _patch_runtime, monkeypatch |
| `test_panel_is_constructible_against_the_stand_alone_host` | 1 | _patch_runtime, monkeypatch |
| `test_here_the_panel_is_the_window_so_the_frame_is_the_way_off_it` | 1 | _patch_runtime, monkeypatch |
| `test_start_spawns_no_thread_and_queues_the_sync_callback` | 1 | _patch_runtime, monkeypatch |
| `test_run_window_runs_the_inherited_loop_on_the_calling_thread` | 1 | _patch_runtime, monkeypatch |
| `test_run_window_refuses_a_worker_thread` | 1 | _patch_runtime, monkeypatch |
| `test_draining_the_queued_message_applies_the_title_and_notifies_the_panel` | 1 | _patch_runtime, monkeypatch |
| `test_on_synchronized_is_safe_with_no_app_and_no_panel` | 1 | _patch_runtime, monkeypatch |
| `test_build_gui_seeds_sync_pending_from_the_hosts_synchronized_state` | 2 | _patch_runtime, expected, monkeypatch, synchronized |
| `test_closing_the_panel_closes_the_window_it_is_the_whole_of` | 1 | _patch_runtime, monkeypatch |
| `test_host_destroy_gui_releases_the_panel` | 1 | _patch_runtime, monkeypatch |

## tests/cli/test_make_gui.py

32 cases; 29 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_parse_wide_screen_set_normalizes_aliases_and_dedupes` | 1 |  |
| `test_parse_wide_screen_set_accepts_alternate_delimiters` | 1 |  |
| `test_parse_wide_screen_set_accepts_operating_accessories_aliases` | 1 |  |
| `test_parse_wide_screen_set_rejects_unknown_component` | 1 |  |
| `test_harvest_gui_config_includes_screen_components` | 1 |  |
| `test_make_gui_parser_accepts_no_cache_sync` | 1 |  |
| `test_make_gui_command_line_defaults_to_cache_sync_enabled` | 1 |  |
| `test_make_gui_command_line_can_disable_cache_sync` | 1 |  |
| `test_make_gui_shell_script_includes_cache_sync_switch_only_when_disabled` | 1 | launcher_factory, tmp_path, tmp_path_factory |
| `test_shell_script_renders_packaged_template_from_another_working_directory` | 1 | launcher_factory, monkeypatch, tmp_path, tmp_path_factory |
| `test_landscape_aliases_template_and_font_selection` | 1 |  |
| `test_project_packages_digital_dream_fonts` | 1 |  |
| `test_harvest_landscape_config_includes_native_size_and_profile` | 1 |  |
| `test_make_gui_parser_constructs_landscape_controller` | 1 |  |
| `test_font_install_uses_xdg_directory_refreshes_and_verifies` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_steam_deck_gui_reports_its_platform` | 1 |  |
| `test_other_guis_imply_no_platform` | 3 | gui_class |
| `test_launch_template_exposes_the_platform_placeholder` | 1 |  |
| `test_shell_script_exports_the_platform_it_was_generated_for` | 2 | expected, gui_class, launcher_factory, tmp_path, tmp_path_factory |
| `test_postprocess_config_records_the_platform` | 1 |  |
| `test_landscape_omits_desktop_autostart_by_default` | 1 |  |
| `test_landscape_installs_desktop_autostart_when_asked` | 1 |  |
| `test_desktop_autostart_abbreviates` | 1 |  |
| `test_other_guis_still_autostart_unconditionally` | 1 |  |
| `test_install_without_autostart_removes_a_stale_entry` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_install_with_autostart_writes_the_entry` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_install_aborts_when_the_autostart_entry_cannot_be_written` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_gui_is_present_with_only_a_launcher` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_gui_is_absent_when_nothing_was_installed` | 1 | tmp_path, tmp_path_factory |

## tests/cli/test_make_service.py

4 cases; 4 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestMakeService::test_parser` | 1 | _xunit_setup_method_fixture_TestMakeService |
| `test_make_service_command_line_defaults_to_cache_sync_enabled` | 1 |  |
| `test_make_service_command_line_can_disable_cache_sync` | 1 |  |
| `test_make_service_shell_script_includes_cache_sync_switch_only_when_disabled` | 1 | tmp_path, tmp_path_factory |

## tests/cli/test_pycab.py

59 cases; 39 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_parser_leaves_the_window_unsized_so_it_can_be_fitted_to_the_display` | 1 |  |
| `test_parser_accepts_each_connection_and_window_option` | 9 | attribute, cmd_line, expected |
| `test_the_help_renders_rather_than_raising_on_its_own_text` | 1 |  |
| `test_the_shape_helpers_keep_the_panel_proportioned_as_the_pi_draws_it` | 1 |  |
| `test_the_text_scale_tracks_the_width_from_the_pis_pairing` | 5 | expected, width |
| `test_the_window_is_the_largest_of_that_shape_the_work_area_holds` | 1 |  |
| `test_the_macos_window_takes_only_its_share_of_the_work_area` | 1 |  |
| `test_a_display_with_room_to_spare_gets_exactly_what_the_pi_gets` | 1 |  |
| `test_a_work_area_narrower_than_it_is_tall_binds_the_width_instead` | 1 |  |
| `test_the_window_stops_shrinking_where_the_layout_stops_shrinking` | 1 |  |
| `test_an_unsized_window_is_fitted_to_the_screen_and_scaled_to_the_fit` | 1 |  |
| `test_a_width_on_its_own_settles_both_the_height_and_the_scale` | 1 |  |
| `test_a_height_on_its_own_settles_the_width` | 1 |  |
| `test_what_was_asked_for_is_honored_and_the_screen_left_unmeasured` | 1 | monkeypatch |
| `test_no_display_to_measure_leaves_the_design_size` | 1 | monkeypatch |
| `test_the_screen_measurement_reports_nothing_rather_than_failing` | 1 | monkeypatch |
| `test_the_screen_measurement_is_capped_by_the_screen_itself` | 1 | monkeypatch |
| `test_the_cli_settles_the_window_from_the_arguments_it_was_given` | 1 |  |
| `test_main_returns_zero_and_passes_its_arguments_through` | 1 | monkeypatch |
| `test_main_reads_sys_argv_when_given_nothing` | 1 | monkeypatch |
| `test_main_exits_rather_than_raising_when_the_cli_fails` | 1 | monkeypatch |
| `test_command_discovers_only_when_base_has_no_address` | 8 | cmd_line, discovers, expected_base, monkeypatch |
| `test_command_does_not_fall_back_to_client_when_no_base_is_found` | 1 | monkeypatch |
| `test_send_opens_the_window_with_the_requested_geometry_and_runs_its_loop` | 1 | monkeypatch |
| `test_send_waits_for_sync_and_shuts_pytrain_down_afterwards` | 1 | monkeypatch |
| `test_send_builds_no_requests` | 1 |  |
| `test_start_queues_the_title_update_rather_than_spawning_the_tk_thread` | 1 |  |
| `test_on_synchronized_applies_the_title_once_the_app_exists` | 1 |  |
| `test_run_window_refuses_to_own_the_tk_loop_off_the_main_thread` | 1 |  |
| `test_run_window_runs_the_inherited_loop_on_the_main_thread` | 1 | monkeypatch |
| `test_the_desktop_window_reserves_the_info_rows_own_height` | 1 |  |
| `test_a_panel_with_no_info_row_yet_reserves_nothing` | 2 | view |
| `test_a_row_that_cannot_be_measured_reserves_nothing` | 1 |  |
| `test_the_desktop_keys_are_smaller_than_the_touchscreens` | 1 |  |
| `test_a_caller_may_still_ask_for_a_different_key_size` | 1 | monkeypatch |
| `test_the_desktop_window_draws_a_picture_at_its_own_proportions` | 1 |  |
| `test_the_desktop_window_lets_a_panel_that_will_not_fit_cover_the_id_row` | 1 |  |
| `test_the_desktop_admin_footer_leaves_room_for_native_controls` | 1 |  |
| `test_the_desktop_window_grows_a_title_row_to_the_title_in_it` | 1 |  |

## tests/cli/test_pytrain.py

40 cases; 15 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_server_startup` | 4 | args, bare_pytrain, base, monkeypatch, port, pytrain_isolation, pytrain_startup, ser2 |
| `test_client_startup` | 2 | bare_pytrain, explicit, monkeypatch, pytrain_isolation, pytrain_startup |
| `test_startup_options_and_api_handoff` | 1 | bare_pytrain, monkeypatch, pytrain_isolation, pytrain_startup |
| `test_startup_uses_process_arguments` | 2 | args, bare_pytrain, monkeypatch, pytrain_isolation, pytrain_startup |
| `test_discovery_failure_precedes_services` | 2 | args, bare_pytrain, dependency, error, monkeypatch, pytrain_isolation, pytrain_startup, text |
| `test_transport_failure_does_not_register_current` | 1 | bare_pytrain, monkeypatch, pytrain_isolation, pytrain_startup |
| `test_current_before_initialization` | 1 | bare_pytrain, pytrain_isolation |
| `test_parser_defaults` | 1 | bare_pytrain, pytrain_isolation |
| `test_parser_rejects_invalid_options` | 7 | args, bare_pytrain, pytrain_isolation |
| `test_parser_version_and_optional_files` | 4 | bare_pytrain, capsys, extended, monkeypatch, packaged, pytrain_isolation |
| `test_basic_properties_and_representation` | 3 | args, bare_pytrain, base, monkeypatch, pytrain_isolation, pytrain_startup, role |
| `test_client_base_address_and_version_without_server` | 1 | bare_pytrain, monkeypatch, pytrain_isolation, pytrain_startup |
| `test_api_active_requires_all_components` | 4 | api, bare_pytrain, expected, pytrain_isolation, queue, thread |
| `test_exit_status_and_exception` | 6 | status, value |
| `test_isolation_restores_state_after_exception` | 1 |  |

## tests/cli/test_pytrain_admin.py

134 cases; 25 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_callback_admin_deduplication` | 28 | admin, api, bare_pytrain, command, monkeypatch, pytrain_isolation |
| `test_callback_echo_non_admin` | 4 | admin, bare_pytrain, echo_error, monkeypatch, pytrain_isolation |
| `test_api_callback_cache_failure_warns_and_notifies_once` | 6 | admin, api_cache_shutdown, bare_pytrain, caplog, command, monkeypatch, pytrain_isolation, status |
| `test_api_callback_cache_failure_blocks_handoff_and_allows_retry` | 2 | admin, api_cache_shutdown, bare_pytrain, caplog, monkeypatch, pytrain_isolation |
| `test_targeted_admin` | 8 | admin, bare_pytrain, dispatcher, monkeypatch, port, pytrain_isolation, target |
| `test_invalid_target_port` | 2 | admin, bare_pytrain, monkeypatch, pytrain_isolation |
| `test_admin_broadcast_and_local_routing` | 16 | admin, args, bare_pytrain, command, monkeypatch, pytrain_isolation |
| `test_client_on_server_host` | 2 | admin, bare_pytrain, monkeypatch, pytrain_isolation |
| `test_restart` | 4 | admin, bare_pytrain, interrupt, monkeypatch, pytrain_isolation |
| `test_relaunch_api` | 12 | admin, bare_pytrain, monkeypatch, pytrain_isolation, status |
| `test_service_detection` | 6 | admin, bare_pytrain, linux, monkeypatch, pytrain_isolation, returncode |
| `test_service_relaunch` | 2 | admin, bare_pytrain, monkeypatch, pytrain_isolation |
| `test_command_line_relaunch_preserves_arguments` | 8 | admin, bare_pytrain, enabled, monkeypatch, present, pytrain_isolation |
| `test_callback_records_action_and_shuts_down_before_interrupt` | 2 | admin, bare_pytrain, monkeypatch, pytrain_isolation |
| `test_local_exit_suppresses_immediate_and_late_echoes` | 8 | admin, api, bare_pytrain, command, monkeypatch, pytrain_isolation |
| `test_simultaneous_exiting_callbacks_accept_one_action` | 2 | admin, bare_pytrain, monkeypatch, pytrain_isolation |
| `test_failed_local_dispatch_can_be_retried` | 2 | admin, bare_pytrain, monkeypatch, pytrain_isolation |
| `test_client_me_waits_for_callback` | 4 | admin, bare_pytrain, monkeypatch, pytrain_isolation, same_host |
| `test_routing_cannot_replace_committed_action` | 2 | admin, bare_pytrain, monkeypatch, pytrain_isolation |
| `test_shutdown_suppresses_unclaimed_callback` | 2 | admin, bare_pytrain, monkeypatch, pytrain_isolation |
| `test_signal_diagnostic_precedes_send` | 2 | admin, bare_pytrain, caplog, monkeypatch, pytrain_isolation |
| `test_api_callback_notification_is_one_shot` | 2 | admin, bare_pytrain, caplog, monkeypatch, pytrain_isolation |
| `test_local_api_exit_does_not_notify_until_handoff` | 2 | admin, bare_pytrain, monkeypatch, pytrain_isolation |
| `test_relaunch_os_errors_propagate` | 4 | admin, bare_pytrain, monkeypatch, pytrain_isolation, service |
| `test_server_gui_quit_broadcasts_then_signals_local_exit` | 2 | admin, bare_pytrain, monkeypatch, pytrain_isolation |

## tests/cli/test_pytrain_commands.py

94 cases; 21 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_command_registry` | 36 | name, target |
| `test_special_routing` | 7 | args, bare_pytrain, command_train, method, monkeypatch, pytrain_isolation, text |
| `test_special_outputs_and_pdi_error` | 1 | bare_pytrain, caplog, capsys, command_train, monkeypatch, pytrain_isolation |
| `test_empty_command` | 3 | bare_pytrain, command_train, monkeypatch, pytrain_isolation, text |
| `test_missing_and_admin_parse` | 1 | bare_pytrain, command_train, monkeypatch, pytrain_isolation |
| `test_parse_errors` | 7 | bare_pytrain, capsys, command_train, monkeypatch, pytrain_isolation, text |
| `test_parse_failure_mode_isolation` | 6 | bare_pytrain, capsys, command_train, diagnostic, help_text, invalid, monkeypatch, pytrain_isolation |
| `test_real_parse_only` | 6 | bare_pytrain, command_train, monkeypatch, pytrain_isolation, scope, text, tmcc |
| `test_infer_engine_mode` | 2 | bare_pytrain, command_train, is_tmcc, monkeypatch, pytrain_isolation |
| `test_parser_restored` | 2 | bare_pytrain, command_train, monkeypatch, pytrain_isolation, text |
| `test_normal_send` | 1 | bare_pytrain, caplog, command_train, monkeypatch, pytrain_isolation |
| `test_help` | 3 | bare_pytrain, capsys, command_train, monkeypatch, pytrain_isolation, text |
| `test_quit_routing` | 3 | bare_pytrain, command_train, monkeypatch, pytrain_isolation, server, target |
| `test_admin_routing` | 1 | bare_pytrain, command_train, monkeypatch, pytrain_isolation |
| `test_decode_and_send` | 2 | bare_pytrain, capsys, command_train, monkeypatch, pdi, pytrain_isolation |
| `test_decode_invalid` | 4 | bare_pytrain, command_train, monkeypatch, pytrain_isolation, text |
| `test_invalid_constructed_command` | 2 | bare_pytrain, caplog, command_train, monkeypatch, parse_only, pytrain_isolation |
| `test_subparser_mode_inference` | 2 | bare_pytrain, command_train, monkeypatch, prefix, pytrain_isolation |
| `test_send_without_debug` | 1 | bare_pytrain, caplog, command_train, monkeypatch, pytrain_isolation |
| `test_invalid_admin_enum` | 3 | text |
| `test_client_resync_routing` | 1 | bare_pytrain, command_train, monkeypatch, pytrain_isolation |

## tests/cli/test_pytrain_debug_toggle.py

32 cases; 5 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_debug_toggle_moves_every_module_logger` | 1 | root_at_info |
| `test_debug_property_toggles_through_the_same_path` | 1 | root_at_info |
| `test_toggle_handlers` | 20 | bare_pytrain, enabled, feature, initial, monkeypatch, parts, pytrain_isolation |
| `test_toggle_properties_noop_and_transition` | 8 | bare_pytrain, feature, initial, monkeypatch, pytrain_isolation, value |
| `test_echo_subscriptions` | 2 | bare_pytrain, pdi, pytrain_isolation |

## tests/cli/test_pytrain_pdi.py

140 cases; 7 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_pdi_requests` | 117 | bare_pytrain, caplog, expected, mode, pytrain_isolation, text, transport |
| `test_incomplete_pdi_is_noop` | 4 | bare_pytrain, pytrain_isolation, text, transport |
| `test_invalid_pdi` | 9 | bare_pytrain, error, pytrain_isolation, text, transport |
| `test_invalid_pdi_values` | 7 | bare_pytrain, pytrain_isolation, text, transport |
| `test_debug_base_record_current_failure` | 1 | bare_pytrain, caplog, pytrain_isolation, transport |
| `test_debug_pdi_dispatch` | 1 | bare_pytrain, caplog, pytrain_isolation, transport |
| `test_d4_clear_is_currently_noop` | 1 | bare_pytrain, pytrain_isolation, transport |

## tests/cli/test_pytrain_runtime.py

148 cases; 31 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_runtime_modes` | 3 | bare_pytrain, mode, monkeypatch, pytrain_isolation, runtime |
| `test_server_startup_order` | 4 | available, bare_pytrain, enabled, manager, monkeypatch, pytrain_isolation, runtime |
| `test_client_state_precedes_buttons` | 1 | bare_pytrain, monkeypatch, pytrain_isolation, runtime |
| `test_update_required_client` | 1 | bare_pytrain, monkeypatch, pytrain_isolation, runtime |
| `test_startup_update_interrupt_runs_full_shutdown` | 1 | bare_pytrain, monkeypatch, pytrain_isolation, runtime |
| `test_escaping_cleanup_error_never_dispatches_action` | 50 | action, bare_pytrain, error, monkeypatch, pytrain_isolation, runtime, stage |
| `test_echo_while_cache_shutdown_waits_finishes_cleanup_before_update` | 1 | bare_pytrain, caplog, monkeypatch, pytrain_isolation, real_exit_runtime, runtime |
| `test_interrupted_full_shutdown_retries_cache_but_never_updates` | 2 | bare_pytrain, monkeypatch, pytrain_isolation, real_exit_runtime, retry_interrupted, runtime |
| `test_failed_cache_stop_warns_and_continues_to_update` | 1 | bare_pytrain, caplog, monkeypatch, pytrain_isolation, real_exit_runtime, runtime |
| `test_retained_cache_without_exception_warns_and_continues` | 1 | bare_pytrain, caplog, monkeypatch, pytrain_isolation, runtime |
| `test_final_subsystem_failures_are_independent` | 3 | bare_pytrain, cache_failure, caplog, monkeypatch, pytrain_isolation, runtime, service_failure |
| `test_interactive_parser_errors_continue` | 2 | bare_pytrain, error, monkeypatch, pytrain_isolation, runtime |
| `test_api_queue_accounting` | 4 | bare_pytrain, error, monkeypatch, pytrain_isolation, runtime |
| `test_api_handler_can_clear_queue` | 1 | bare_pytrain, monkeypatch, pytrain_isolation, runtime |
| `test_replay_once_continues_after_parser_errors` | 1 | bare_pytrain, monkeypatch, pytrain_isolation, runtime, tmp_path, tmp_path_factory |
| `test_missing_replay_continues` | 1 | bare_pytrain, caplog, monkeypatch, pytrain_isolation, runtime, tmp_path, tmp_path_factory |
| `test_deferred_actions_after_cleanup` | 6 | action, bare_pytrain, kwargs, method, monkeypatch, pytrain_isolation, runtime |
| `test_unexpected_runtime_errors_still_close_service_and_cache` | 6 | bare_pytrain, cache_failure, monkeypatch, pytrain_isolation, runtime, source |
| `test_runtime_finalization_repeats_helpers_without_repeating_successful_cleanup` | 2 | bare_pytrain, cache_failure, caplog, monkeypatch, pytrain_isolation, runtime |
| `test_queue_command_routing` | 5 | api, bare_pytrain, command, monkeypatch, pytrain_isolation, queue_present, runtime |
| `test_buttons_loader` | 4 | bare_pytrain, caplog, expected, monkeypatch, pytrain_isolation, script, tmp_path, tmp_path_factory |
| `test_shutdown_continues_after_individual_failure` | 10 | bare_pytrain, caplog, failure, monkeypatch, pytrain_isolation, runtime |
| `test_shutdown_real_helpers_isolate_failures_and_retry` | 6 | bare_pytrain, cache_failure, caplog, monkeypatch, pytrain_isolation, runtime, service_failure |
| `test_shutdown_without_client_or_queue` | 3 | api, bare_pytrain, monkeypatch, port, pytrain_isolation, runtime, server |
| `test_service_shutdown_failure_boundaries` | 3 | bare_pytrain, failure, monkeypatch, pytrain_isolation, runtime |
| `test_service_shutdown_without_registration` | 3 | bare_pytrain, info, monkeypatch, pytrain_isolation, runtime, zeroconf |
| `test_queued_api_exit_publishes_status_before_one_host_notification` | 12 | action, bare_pytrain, monkeypatch, pytrain_isolation, runtime, server |
| `test_queued_api_exit_suppresses_echoes_and_late_actions` | 2 | bare_pytrain, monkeypatch, pytrain_isolation, runtime, server |
| `test_queued_api_exit_skips_notification_when_cleanup_escapes` | 7 | bare_pytrain, error, monkeypatch, pytrain_isolation, runtime, stage |
| `test_queued_api_exit_skips_notification_when_deferred_action_fails` | 1 | bare_pytrain, monkeypatch, pytrain_isolation, runtime |
| `test_callback_only_api_exit_still_notifies_once` | 1 | bare_pytrain, monkeypatch, pytrain_isolation, runtime |

## tests/cli/test_pytrain_service_discovery.py

26 cases; 12 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_added_service_is_recorded_with_the_root_logger_at_info` | 1 | root_at_info |
| `test_added_service_is_recorded_with_the_root_logger_at_debug` | 1 | caplog |
| `test_added_service_without_info_is_a_no_op` | 1 | root_at_info |
| `test_discovery_requires_network_readiness` | 1 | bare_pytrain, caplog, discovery, monkeypatch, pytrain_isolation |
| `test_discovery_prefers_combined_server_and_records_cache_capability` | 6 | bare_pytrain, caplog, discovery, headless, level, monkeypatch, pytrain_isolation |
| `test_discovery_allows_combined_server_to_arrive_after_base_only` | 1 | bare_pytrain, discovery, monkeypatch, pytrain_isolation |
| `test_discovery_falls_back_to_base_only_after_more_than_fifteen_seconds` | 1 | bare_pytrain, discovery, monkeypatch, pytrain_isolation |
| `test_discovery_timeout_is_bounded_and_rejects_servers_without_base` | 6 | bare_pytrain, caplog, discovery, headless, monkeypatch, properties, pytrain_isolation |
| `test_discovery_errors_are_logged_and_resources_closed` | 3 | bare_pytrain, caplog, discovery, monkeypatch, pytrain_isolation, source |
| `test_discovery_cleanup_errors_propagate_but_cancel_failure_still_closes` | 2 | bare_pytrain, discovery, monkeypatch, pytrain_isolation, source |
| `test_zeroconf_construction_error_propagates_without_starting_browser` | 1 | bare_pytrain, discovery, monkeypatch, pytrain_isolation |
| `test_other_state_changes_do_not_query_or_record` | 2 | root_at_info, state_change |

## tests/cli/test_pytrain_state.py

46 cases; 9 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_synchronized` | 3 | bare_pytrain, pytrain_isolation, state_train, value |
| `test_load_client_state` | 9 | bare_pytrain, capsys, headless, known_server, monkeypatch, no_wait, pytrain_isolation, state_train, sync |
| `test_roster_requests` | 12 | bare_pytrain, capsys, monkeypatch, no_wait, pytrain_isolation, startup, state_train, sync |
| `test_db_filters` | 8 | bare_pytrain, capsys, pytrain_isolation, query, state_train |
| `test_db_address` | 2 | bare_pytrain, capsys, found, pytrain_isolation, state_train |
| `test_empty_database` | 6 | bare_pytrain, capsys, params, pytrain_isolation, state_train |
| `test_database_counts_and_lcs` | 1 | bare_pytrain, capsys, pytrain_isolation, state_train |
| `test_product_lookup` | 4 | available, bare_pytrain, caplog, monkeypatch, pytrain_isolation, state_kind, state_train |
| `test_query_errors_and_empty_info` | 1 | bare_pytrain, caplog, pytrain_isolation, state_train |

## tests/cli/test_pytrain_update.py

71 cases; 28 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_api_power_records_status_without_subprocess` | 2 | commands, monkeypatch, reboot, status |
| `test_api_update_upgrades_pip_before_exit` | 1 | commands, monkeypatch |
| `test_package_update_fallback_and_failed_commands` | 2 | monkeypatch, returncode |
| `test_update_subprocess_exception_propagates` | 1 | monkeypatch |
| `test_update_ignores_late_exit_callbacks_during_subprocess_wait` | 30 | bare_pytrain, claimed_update, is_package, late_action, monkeypatch, pytrain_isolation, repo_root, tmp_path, tmp_path_factory, wait_command |
| `test_update_subprocess_keyboard_interrupt_propagates_without_retry_or_relaunch` | 5 | bare_pytrain, claimed_update, is_package, monkeypatch, pytrain_isolation, repo_root, tmp_path, tmp_path_factory, wait_command |
| `test_update_uses_the_gpio_free_requirements_on_the_steam_deck` | 1 | monkeypatch, repo_root, tmp_path, tmp_path_factory |
| `test_update_uses_the_default_requirements_elsewhere` | 1 | monkeypatch, repo_root, tmp_path, tmp_path_factory |
| `test_update_falls_back_when_the_gpio_free_list_is_missing` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_source_update_installs_the_selected_requirements` | 1 | commands, monkeypatch, repo_root, tmp_path, tmp_path_factory |
| `test_package_update_reinstalls_the_installed_distribution` | 2 | commands, monkeypatch, package |
| `test_requirements_files_both_exist_in_the_repo` | 1 |  |
| `test_reboot_asks_shutdown_to_restart` | 1 | commands, monkeypatch |
| `test_shutdown_omits_the_restart_flag` | 1 | commands, monkeypatch |
| `test_upgrade_updates_pytrain_before_touching_the_os` | 1 | commands, monkeypatch |
| `test_upgrade_off_linux_updates_and_relaunches` | 1 | commands, monkeypatch |
| `test_upgrade_in_api_mode_signals_without_acting` | 1 | commands, monkeypatch |
| `test_relaunch_restarts_the_service_when_running_as_one` | 1 | commands, monkeypatch |
| `test_relaunch_execs_itself_when_not_a_service` | 1 | commands, monkeypatch |
| `test_is_service_reads_the_systemctl_returncode` | 2 | expected, monkeypatch, returncode |
| `test_is_service_is_false_off_linux` | 1 | commands, monkeypatch |
| `test_upgrade_skips_the_os_on_the_steam_deck` | 1 | commands, monkeypatch |
| `test_update_relaunches_only_when_asked` | 2 | commands, monkeypatch, relaunch, repo_root, tmp_path, tmp_path_factory |
| `test_steam_deck_powers_down_through_logind` | 2 | commands, expected, monkeypatch, reboot |
| `test_the_pi_command_is_unchanged_by_the_deck_branch` | 1 | monkeypatch |
| `test_a_failed_power_command_is_logged` | 1 | caplog, monkeypatch |
| `test_externally_managed_update_never_runs_commands_or_relaunches` | 4 | caplog, commands, is_api, is_package, monkeypatch |
| `test_externally_managed_upgrade_never_runs_commands_or_reboots` | 2 | caplog, commands, is_api, monkeypatch |

## tests/cli/test_routes.py

48 cases; 18 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_parser_defaults_to_a_client_with_no_window_overrides` | 1 |  |
| `test_parser_help_describes_the_default_window_size` | 1 |  |
| `test_parser_accepts_each_connection_and_window_option` | 9 | attribute, cmd_line, expected |
| `test_parser_rejects_invalid_options` | 5 | cmd_line |
| `test_cli_initializes_a_system_command_without_building_requests` | 4 | cmd_line, connection, gui_class, monkeypatch, pytrain |
| `test_cli_forwards_logging_flags` | 3 | debug, echo, flags, gui_class, monkeypatch, pytrain |
| `test_cli_honors_do_fire_and_forwards_connection_options` | 2 | do_fire, monkeypatch, pytrain |
| `test_fire_runs_the_window_synchronously_on_the_main_thread_then_shuts_down` | 1 | gui_class, monkeypatch, pytrain |
| `test_send_shuts_down_when_window_creation_or_run_fails` | 6 | error_type, failure_point, gui_class, monkeypatch, pytrain |
| `test_gui_import_is_lazy_and_import_failure_still_shuts_down` | 1 | monkeypatch, pytrain |
| `test_send_handles_an_absent_pytrain` | 1 | gui_class, monkeypatch, pytrain |
| `test_main_returns_zero_and_passes_its_arguments_through` | 3 | args, monkeypatch |
| `test_main_reads_sys_argv_when_given_nothing` | 1 | monkeypatch |
| `test_main_reports_gui_errors_after_cleanup` | 4 | error_type, failure_point, gui_class, monkeypatch, pytrain |
| `test_main_reports_connection_initialization_errors` | 1 | monkeypatch |
| `test_main_preserves_parser_exit_codes_without_starting_pytrain` | 2 | args, exit_code, monkeypatch, pytrain |
| `test_source_launcher_uses_main` | 1 | monkeypatch |
| `test_source_launcher_help_without_pythonpath` | 2 | from_root, tmp_path, tmp_path_factory |

## tests/comm/test_comm_buffer_proxy_disconnect.py

7 cases; 7 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_normal_command_sent_on_first_connection` | 1 | fake_socket, mock_comm_external_io, monkeypatch, proxy |
| `test_normal_command_retries_transient_connection_failure` | 1 | fake_socket, mock_comm_external_io, monkeypatch, proxy |
| `test_normal_command_raises_after_retry_limit` | 1 | fake_socket, mock_comm_external_io, monkeypatch, proxy |
| `test_normal_command_retains_default_retry_limit` | 1 | fake_socket, mock_comm_external_io, monkeypatch, proxy |
| `test_disconnect_sends_request_when_server_available` | 1 | fake_socket, mock_comm_external_io, monkeypatch, proxy |
| `test_disconnect_does_not_retry_when_server_unavailable` | 1 | fake_socket, mock_comm_external_io, monkeypatch, proxy |
| `test_disconnect_stops_heartbeat_before_attempting_send` | 1 | fake_socket, mock_comm_external_io, monkeypatch, proxy |

## tests/comm/test_command_listener.py

4 cases; 4 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestCommandListener::test_command_listener_singleton` | 1 | _xunit_setup_method_fixture_TestCommandListener, mock_comm_external_io, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestCommandListener::test_command_listener_build` | 1 | _xunit_setup_method_fixture_TestCommandListener, mock_comm_external_io, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestCommandListener::test_command_listener_invalid_baudrate` | 1 | _xunit_setup_method_fixture_TestCommandListener, mock_comm_external_io, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestCommandListener::test_command_listener_run` | 1 | _xunit_setup_method_fixture_TestCommandListener, mock_comm_external_io, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |

## tests/comm/test_command_listener_ai.py

5 cases; 5 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_decode_tmcc1_three_byte_command` | 1 | mock_comm_external_io, monkeypatch, reset_listener_singleton |
| `test_decode_tmcc2_three_byte_engine_command` | 1 | mock_comm_external_io, monkeypatch, reset_listener_singleton |
| `test_decode_tmcc2_four_digit_address_command_sets_tmcc4` | 1 | mock_comm_external_io, monkeypatch, reset_listener_singleton |
| `test_decode_tmcc2_multibyte_parameter_command` | 1 | mock_comm_external_io, monkeypatch, reset_listener_singleton |
| `test_decode_admin_sync_command_restart_flows_through_deque` | 1 | mock_comm_external_io, monkeypatch, reset_listener_singleton |

## tests/comm/test_dispatch_listener.py

28 cases; 9 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestCommandDispatcher::test_command_dispatcher_singleton` | 1 | _xunit_setup_method_fixture_TestCommandDispatcher, mock_comm_external_io, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestCommandDispatcher::test_command_dispatcher_run` | 1 | _xunit_setup_method_fixture_TestCommandDispatcher, mock_comm_external_io, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestCommandDispatcher::test_channel_class` | 1 | _xunit_setup_method_fixture_TestCommandDispatcher, mock_comm_external_io, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestCommandDispatcher::test_publish_all` | 1 | _xunit_setup_method_fixture_TestCommandDispatcher, mock_comm_external_io, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestCommandDispatcher::test_publish` | 1 | _xunit_setup_method_fixture_TestCommandDispatcher, mock_comm_external_io, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestCommandDispatcher::test_publish_halt` | 1 | _xunit_setup_method_fixture_TestCommandDispatcher, mock_comm_external_io, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestCommandDispatcher::test_publish_system_halt` | 1 | _xunit_setup_method_fixture_TestCommandDispatcher, mock_comm_external_io, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestCommandDispatcher::test_client_broadcast_preserves_echo_source` | 20 | _xunit_setup_method_fixture_TestCommandDispatcher, address, command, is_rx, mock_comm_external_io, run_before_and_after_tests, scope, tmp_path, tmp_path_factory, tmpdir |
| `TestCommandDispatcher::test_update_client_state_skips_when_proxy_receiver_not_built` | 1 | _xunit_setup_method_fixture_TestCommandDispatcher, mock_comm_external_io, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |

## tests/comm/test_enqueue_proxy_requests.py

16 cases; 9 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_build_request_register_with_uuid_and_version` | 1 | mock_comm_external_io, monkeypatch, reset_singleton |
| `test_build_request_disconnect_with_uuid_no_version` | 1 | mock_comm_external_io, monkeypatch, reset_singleton |
| `test_build_request_sync_state_minimal_defaults` | 1 | mock_comm_external_io, monkeypatch, reset_singleton |
| `test_extract_addendum_variants_port_uuid_and_version` | 8 | cmd_enum, mock_comm_external_io, monkeypatch, reset_singleton |
| `test_extract_addendum_port_and_uuid_only` | 1 | mock_comm_external_io, monkeypatch, reset_singleton |
| `test_extract_addendum_ip_port_text` | 1 | mock_comm_external_io, monkeypatch, reset_singleton |
| `test_extract_addendum_port_only_two_bytes` | 1 | mock_comm_external_io, monkeypatch, reset_singleton |
| `test_client_session_tracking_connect_disconnect_and_replace` | 1 | mock_comm_external_io, monkeypatch, reset_singleton |
| `test_enqueue_request_forwards_to_buffer` | 1 | mock_comm_external_io, monkeypatch, reset_singleton |

## tests/db/test_accessory_state.py

18 cases; 18 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestAccessoryState::test_invalid_scope_rejected` | 1 | mock_command_dispatcher_ip |
| `TestAccessoryState::test_tmcc_aux_updates_and_numeric` | 1 | mock_command_dispatcher_ip |
| `TestAccessoryState::test_relative_speed_updates_and_halt_resets` | 1 | mock_command_dispatcher_ip |
| `TestAccessoryState::test_bpc2_control3_sets_block_power_and_on_off` | 1 | mock_command_dispatcher_ip |
| `TestAccessoryState::test_bpc2_control1_causes_error` | 1 | mock_command_dispatcher_ip |
| `TestAccessoryState::test_asc2_control1_marks_lcs_on_power` | 1 | mock_command_dispatcher_ip |
| `TestAccessoryState::test_amc2_motor_marks_lcs_on_power` | 1 | mock_command_dispatcher_ip |
| `TestAccessoryState::test_irda_marks_sensor_track_and_serialization_includes_irda` | 1 | mock_command_dispatcher_ip |
| `TestAccessoryState::test_irda_config_marks_sensor_track` | 1 | mock_command_dispatcher_ip |
| `TestAccessoryState::test_as_bytes_tmcc_accessory_commands_append` | 1 | mock_command_dispatcher_ip |
| `TestAccessoryState::test_as_dict_accessory_and_sensor_types` | 1 | mock_command_dispatcher_ip |
| `TestAccessoryState::test_payload_renders_reasonable_info` | 1 | mock_command_dispatcher_ip |
| `TestAccessoryState::test_halt_resets_aux_and_number` | 1 | mock_command_dispatcher_ip |
| `TestAccessoryState::test_tmcc_commands_ignored_after_pdi_source` | 1 | mock_command_dispatcher_ip |
| `TestAccessoryState::test_payload_for_asc2_includes_prefix_for_on_and_off` | 1 | mock_command_dispatcher_ip |
| `TestAccessoryState::test_as_bytes_lcs_asc2_uses_first_action_and_value` | 1 | mock_command_dispatcher_ip |
| `TestAccessoryState::test_as_bytes_amc2_includes_numeric_when_set` | 1 | mock_command_dispatcher_ip |
| `TestAccessoryState::test_get_motor_and_lamps_none_when_not_amc2` | 1 | mock_command_dispatcher_ip |

## tests/db/test_cache_sync.py

43 cases; 29 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_default_cache_sync_poll_interval_is_30_seconds` | 1 | mock_command_dispatcher_ip |
| `test_interrupted_cache_stop_retains_resources_and_retries` | 4 | caplog, error, lifecycle, mock_command_dispatcher_ip, monkeypatch, operation |
| `test_stop_without_listener_terminates_real_worker` | 1 | lifecycle, mock_command_dispatcher_ip, monkeypatch |
| `test_serving_thread_start_failure_closes_socket_without_shutdown` | 1 | lifecycle, mock_command_dispatcher_ip, monkeypatch |
| `test_join_timeout_retains_ownership_until_thread_terminates` | 2 | lifecycle, mock_command_dispatcher_ip, monkeypatch, owned_thread |
| `test_stop_from_owned_thread_rejects_self_join_and_retains_manager` | 2 | lifecycle, mock_command_dispatcher_ip, monkeypatch, owned_thread |
| `test_unstarted_threads_are_not_joined` | 1 | lifecycle, mock_command_dispatcher_ip, monkeypatch |
| `test_build_serializes_with_stop_and_retains_failed_stop` | 2 | failure, lifecycle, mock_command_dispatcher_ip, monkeypatch |
| `test_manager_creation_and_listener_logs_are_distinct` | 1 | caplog, capsys, lifecycle, mock_command_dispatcher_ip, monkeypatch |
| `test_sidecar_payload_round_trip_syncs_files_and_deletes_stale_client_cache` | 1 | mock_command_dispatcher_ip, tmp_path, tmp_path_factory |
| `test_sidecar_payload_without_delete_keeps_stale_server_cache` | 1 | mock_command_dispatcher_ip, tmp_path, tmp_path_factory |
| `test_sidecar_payload_syncs_config_json_files` | 1 | mock_command_dispatcher_ip, tmp_path, tmp_path_factory |
| `test_config_sync_ignores_non_json_and_nested_files` | 1 | mock_command_dispatcher_ip, tmp_path, tmp_path_factory |
| `test_config_sync_handles_missing_directories` | 1 | mock_command_dispatcher_ip, tmp_path, tmp_path_factory |
| `test_sync_skips_config_when_peer_does_not_advertise_it` | 1 | mock_command_dispatcher_ip, tmp_path, tmp_path_factory |
| `test_apply_payload_preserves_config_when_payload_does_not_include_config_cache` | 1 | mock_command_dispatcher_ip, tmp_path, tmp_path_factory |
| `test_cache_sync_paths_decode_peer_without_config` | 1 | mock_command_dispatcher_ip, tmp_path, tmp_path_factory |
| `test_sidecar_payload_can_skip_tombstoned_file_names` | 1 | mock_command_dispatcher_ip, tmp_path, tmp_path_factory |
| `test_delete_matching_files_removes_named_files_in_all_cache_subdirs` | 1 | mock_command_dispatcher_ip, tmp_path, tmp_path_factory |
| `test_delete_matching_files_rejects_unsafe_file_names` | 6 | mock_command_dispatcher_ip, tmp_path, tmp_path_factory, unsafe_name |
| `test_sidecar_payload_rejects_unsafe_paths` | 4 | mock_command_dispatcher_ip, tmp_path, tmp_path_factory, unsafe_path |
| `test_cache_sync_paths_round_trip_wire_dict` | 1 | mock_command_dispatcher_ip, tmp_path, tmp_path_factory |
| `test_cache_manifest_uses_config_cache_key` | 1 | mock_command_dispatcher_ip, monkeypatch, tmp_path, tmp_path_factory |
| `test_force_sync_skips_when_client_server_does_not_advertise_support` | 1 | mock_command_dispatcher_ip, monkeypatch |
| `test_client_delete_deletes_local_file_then_forwards_to_server` | 1 | mock_command_dispatcher_ip |
| `test_server_delete_deletes_local_file_then_propagates_to_clients` | 1 | mock_command_dispatcher_ip |
| `test_server_delete_keeps_tombstone_until_client_delete_requests_are_sent` | 1 | mock_command_dispatcher_ip |
| `test_propagated_delete_does_not_log_when_file_is_already_missing` | 1 | caplog, mock_command_dispatcher_ip, monkeypatch, tmp_path, tmp_path_factory |
| `test_sync_to_peer_posts_payload_to_sidecar` | 1 | mock_command_dispatcher_ip, monkeypatch, tmp_path, tmp_path_factory |

## tests/db/test_client_state_listener.py

9 cases; 8 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_singleton_build_returns_same_instance` | 1 | mock_command_dispatcher_ip, monkeypatch, reset_singleton_state |
| `test_offer_routes_to_pdi_when_sop` | 1 | mock_command_dispatcher_ip, monkeypatch, reset_singleton_state |
| `test_subscribe_and_unsubscribe_delegate_to_both_listeners` | 1 | mock_command_dispatcher_ip, reset_singleton_state |
| `test_update_client_if_needed_compares_versions` | 1 | mock_command_dispatcher_ip, monkeypatch, reset_singleton_state |
| `test_client_state_handler_splits_pdi_then_tmcc` | 1 | mock_command_dispatcher_ip, monkeypatch, reset_singleton_state |
| `test_handler_handles_multiple_recv_chunks` | 1 | mock_command_dispatcher_ip, monkeypatch, reset_singleton_state |
| `test_managed_client_warns_about_newer_or_unknown_server_version` | 2 | caplog, mock_command_dispatcher_ip, monkeypatch, reset_singleton_state, server_version |
| `test_managed_client_with_matching_version_has_no_update_warning` | 1 | caplog, mock_command_dispatcher_ip, monkeypatch, reset_singleton_state |

## tests/db/test_comp_data.py

361 cases; 54 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestBitUpdate::test_preserves_other_bits_and_is_idempotent_for_every_byte` | 16 | bit, enabled, isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestBitUpdate::test_rejects_invalid_bit` | 8 | bit, isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestBitUpdate::test_rejects_invalid_byte` | 16 | current, enabled, isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestBitUpdate::test_is_immutable` | 2 | field, isolated_state_store, mock_command_dispatcher_ip, monkeypatch, value |
| `TestCompData::test_route_components_request_is_component_only_and_nonmutating` | 3 | components, isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_route_record_roundtrip_preserves_order_and_metadata` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_route_components_request_rejects_invalid_route_id` | 4 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch, tmcc_id |
| `TestCompData::test_comp_data_handler` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_update_pkg` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_comp_data_from_bytes_factory` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_a_four_digit_train_record_is_read_and_written_with_the_d4_layout` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_a_two_digit_train_record_is_read_and_written_with_the_standard_layout` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_a_record_from_the_d4_channel_needs_a_four_digit_id_to_be_written_back` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_engine_data_is_legacy_flag_and_smoke_mapping` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_engine_data_stores_a_smoke_level_from_either_syntax` | 18 | control_type, isolated_state_store, mock_command_dispatcher_ip, monkeypatch, raw, smoke |
| `TestCompData::test_a_tmcc1_smoke_level_is_stored_as_the_value_the_base_3_is_written` | 2 | isolated_state_store, level, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_engine_data_reads_any_smoke_level_as_on_without_a_legacy_record` | 4 | isolated_state_store, level, mock_command_dispatcher_ip, monkeypatch, raw |
| `TestCompData::test_a_tmcc1_smoke_keypress_writes_the_base_smoke_byte` | 4 | alias, command, data, expected, isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_retired_target_command_has_no_db_updates` | 6 | address, command, isolated_state_store, mock_command_dispatcher_ip, monkeypatch, scope, speed |
| `TestCompData::test_absolute_speed_always_encodes_both_db_speed_fields` | 36 | address, command, expected, is_ramping, isolated_state_store, mock_command_dispatcher_ip, monkeypatch, scope, speed |
| `TestCompData::test_absolute_speed_commands_preserve_target_during_ramp` | 36 | address, command, expected, is_ramping, isolated_state_store, mock_command_dispatcher_ip, monkeypatch, scope, speed |
| `TestCompData::test_direction_updates_preserve_cached_bits_and_serialize` | 72 | address, command, current, data_cls, isolated_state_store, mock_command_dispatcher_ip, monkeypatch, reverse, scope |
| `TestCompData::test_direction_updates_do_not_create_missing_state` | 12 | address, caplog, command, isolated_state_store, mock_command_dispatcher_ip, monkeypatch, scope |
| `TestCompData::test_direction_updates_skip_missing_component_data_or_field` | 8 | caplog, command, comp_data, isolated_state_store, mock_command_dispatcher_ip, monkeypatch, scope |
| `TestCompData::test_direction_updates_skip_unavailable_or_invalid_status` | 24 | caplog, command, current, data_cls, isolated_state_store, mock_command_dispatcher_ip, monkeypatch, scope |
| `TestCompData::test_direction_reads_and_transforms_status_under_state_lock` | 2 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch, scope |
| `TestCompData::test_reset_still_writes_zero_without_cached_state` | 4 | command, isolated_state_store, mock_command_dispatcher_ip, monkeypatch, scope |
| `TestCompData::test_safety_commands_zero_target_regardless_of_ramp_state` | 24 | command, is_ramping, isolated_state_store, mock_command_dispatcher_ip, monkeypatch, scope |
| `TestCompData::test_rpm_labor_updates_preserve_the_other_cached_value` | 4 | command, data, expected, isolated_state_store, mock_command_dispatcher_ip, monkeypatch, scope |
| `TestCompData::test_ordinary_transform_still_receives_command_data` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_engine_data_direction_reads_bit_zero_of_the_soft_status` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_engine_data_direction_is_unknown_without_a_soft_status` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_engine_data_reads_bit_zero_of_a_soft_status_with_every_bit_set` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_engine_data_conversions_basic` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_a_field_whose_last_byte_is_missing_is_not_decoded` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_repr_formats_by_scope` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_as_bytes_round_length_and_padding` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_route_payload_renders_components` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_comp_data_mixin_initialize_sets_types_and_flag` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_comp_data_mixin_initialized_records_serialize` | 5 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch, scope, tmcc_id |
| `TestCompData::test_comp_data_mixin_initialized_route_and_train_have_empty_component_blocks` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_comp_data_mixin_initialize_sets_handler_defaults` | 5 | expected_defaults, isolated_state_store, mock_command_dispatcher_ip, monkeypatch, scope, tmcc_id |
| `TestCompData::test_clear_road_name_number_req_builds_base_memory_update` | 5 | data_cls, expected_scope, expected_start, isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_clear_road_name_number_req_builds_d4_update_for_four_digit_entries` | 2 | data_cls, expected_pdi_command, expected_scope, isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_clear_road_name_number_req_rejects_unmapped_class` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_clear_record_reqs_include_full_record_clear_for_engine_train` | 2 | data_cls, isolated_state_store, mock_command_dispatcher_ip, monkeypatch, scope |
| `TestCompData::test_clear_record_reqs_full_clear_payload_matches_scope_record_size` | 5 | data_cls, isolated_state_store, mock_command_dispatcher_ip, monkeypatch, scope |
| `TestCompData::test_clear_record_reqs_route_uses_state_address_without_raising` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_set_road_number_req_builds_base_memory_update` | 5 | data_cls, expected_start, isolated_state_store, mock_command_dispatcher_ip, monkeypatch, scope |
| `TestCompData::test_set_road_number_req_builds_d4_update_for_four_digit_entries` | 2 | data_cls, expected_pdi_command, isolated_state_store, mock_command_dispatcher_ip, monkeypatch, scope |
| `TestCompData::test_set_road_number_req_with_none_clears_road_number` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_set_road_number_req_rejects_out_of_range_value` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_comp_data_encode_rpm_labor_and_pkg` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |
| `TestCompData::test_missing_attribute_raises_attribute_error` | 1 | isolated_state_store, mock_command_dispatcher_ip, monkeypatch |

## tests/db/test_component_state.py

64 cases; 27 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestComponentState::test_component_state` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_switch_csv` | 12 | _xunit_setup_method_fixture_TestComponentState, include_state, label, mock_command_dispatcher_ip, position, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir, use_subclass |
| `TestComponentState::test_unknown_address_repr` | 3 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, state_cls, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_initialized_address_repr` | 9 | _xunit_setup_method_fixture_TestComponentState, address, mock_command_dispatcher_ip, run_before_and_after_tests, state_cls, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_initial_broadcast_error` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_lcs_mode_and_parent_delegation` | 9 | _xunit_setup_method_fixture_TestComponentState, action, command, mock_command_dispatcher_ip, mode, req_cls, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_serialization_requires_address` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, state_cls, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_optional_address_links_and_order` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_parent_port_requires_addresses` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_non_lcs_states_are_deletable` | 6 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, scope, state_cls, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_lcs_accessory_states_are_not_deletable` | 4 | _xunit_setup_method_fixture_TestComponentState, lcs_req, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_lcs_switch_state_is_not_deletable` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_lcs_train_state_is_not_deletable` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_irda_sensor_track_state_is_not_deletable` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_switch_state` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_route_state_is_known_and_activity` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_uninitialized_route_components_are_empty` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_route_feedback_reconciles_replacement_and_clear` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, monkeypatch, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_route_feedback_propagates_nested_refresh_and_switch_changes` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, monkeypatch, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_accessory_state` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_engine_state` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_train_state` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_an_inactive_comp_data_record_leaves_the_state_reporting_empty` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_an_active_comp_data_record_clears_the_state_reporting_empty` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_system_state_dict` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_component_state_dict` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |
| `TestComponentState::test_state_via_command_dispatcher` | 1 | _xunit_setup_method_fixture_TestComponentState, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |

## tests/db/test_component_state_store.py

1 cases; 1 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestComponentStateStore::test_component_state_store_basic` | 1 | _xunit_setup_method_fixture_TestComponentStateStore, mock_command_dispatcher_ip, run_before_and_after_tests, tmp_path, tmp_path_factory, tmpdir |

## tests/db/test_component_state_store_ai.py

44 cases; 31 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestComponentStateStoreBluetooth::test_lookup_before_build_returns_none` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBluetooth::test_unknown_id_does_not_create_state` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBluetooth::test_record_indexes_the_actual_engine_state` | 4 | address, mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBluetooth::test_shared_id_selects_highest_address_regardless_of_update_order` | 4 | addresses, mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBluetooth::test_different_bluetooth_ids_are_indexed_independently` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBluetooth::test_repeated_record_updates_the_existing_indexed_state` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBluetooth::test_zero_id_is_not_indexed` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBluetooth::test_train_records_do_not_replace_engine_bluetooth_entries` | 2 | address, mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBluetooth::test_command_without_component_data_does_not_create_bluetooth_index` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBasics::test_state_access_requires_a_built_store` | 4 | mock_command_dispatcher_ip, operation, reset_singletons |
| `TestComponentStateStoreBasics::test_build_flags_and_reinitialization` | 4 | is_base, is_ser2, mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBasics::test_query_without_creation_and_state_deletion` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBasics::test_road_number_alias_is_omitted_and_replaced_by_real_engine` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBasics::test_record_number_lookup_uses_engine_records_only` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBasics::test_valid_topic_checks` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBasics::test_build_and_get_singleton` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBasics::test_listen_for_registers_topics_with_listeners` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBasics::test_keys_scopes_addresses_and_get_all_sorting` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBasics::test_component_validations_and_query` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBasics::test_is_empty_property_and_keys` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreBasics::test_set_and_get_state_and_is_state_synchronized` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreUpdates::test_update_single_device` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreUpdates::test_irda_config_marks_corresponding_accessory_as_sensor_track` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreUpdates::test_broadcast_updates_update_all_known_for_scope` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreUpdates::test_halt_updates_all_components_when_not_filtered` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreUpdates::test_halt_filtered_is_suppressed_when_both_base_and_ser2` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestComponentStateStoreUpdates::test_system_halt_updates_engines_and_trains` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestDependencyCacheMappings::test_results_in_and_caused_by_have_known_entries` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestDependencyCacheMappings::test_toggles_and_disabled_by_switch` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `TestDependencyCacheMappings::test_enabled_by_and_disabled_by_for_effects` | 1 | mock_command_dispatcher_ip, reset_singletons |
| `test_thread_safety_basic_concurrent_updates` | 1 | mock_command_dispatcher_ip, reset_singletons |

## tests/db/test_components.py

37 cases; 18 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestConsistComponent::test_as_bytes_and_properties_single_forward` | 1 | mock_command_dispatcher_ip |
| `TestConsistComponent::test_flag_bits_combinations` | 1 | mock_command_dispatcher_ip |
| `TestConsistComponent::test_from_bytes_parses_until_ff_pairs_and_reverses_order` | 1 | mock_command_dispatcher_ip |
| `TestConsistComponent::test_to_bytes_serializes_reversed_and_pads` | 1 | mock_command_dispatcher_ip |
| `TestConsistComponent::test_to_bytes_accepts_empty_components` | 1 | mock_command_dispatcher_ip |
| `TestRouteComponent::test_from_bytes_parses_sorts_by_tmcc_id` | 1 | mock_command_dispatcher_ip |
| `TestRouteComponent::test_ordered_route_roundtrip_with_duplicate_ids_and_flags` | 4 | count, mock_command_dispatcher_ip |
| `TestRouteComponent::test_to_bytes_linear_and_padded` | 1 | mock_command_dispatcher_ip |
| `TestRouteComponent::test_to_bytes_accepts_empty_components` | 1 | mock_command_dispatcher_ip |
| `TestRouteComponent::test_as_signature_switch_and_route` | 1 | mock_command_dispatcher_ip |
| `TestRouteComponent::test_as_request_builds_tmcc1_switch_command` | 1 | mock_command_dispatcher_ip |
| `TestRouteComponent::test_as_bytes_roundtrip` | 1 | mock_command_dispatcher_ip |
| `TestRouteComponent::test_route_block_rejects_overflow` | 1 | mock_command_dispatcher_ip |
| `TestRouteComponent::test_full_route_block_preserves_flags_and_boundary_ids` | 1 | mock_command_dispatcher_ip |
| `TestRouteComponent::test_route_block_ignores_incomplete_pair` | 2 | mock_command_dispatcher_ip, raw |
| `TestRouteComponent::test_route_block_rejects_invalid_ids` | 6 | mock_command_dispatcher_ip, tmcc_id |
| `TestRouteComponent::test_stored_out_variant_is_preserved_and_uses_out_command` | 4 | flags, mock_command_dispatcher_ip |
| `TestRouteComponent::test_route_block_rejects_invalid_flags` | 8 | flags, mock_command_dispatcher_ip |

## tests/db/test_engine_state.py

96 cases; 63 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestEngineStateBehavior::test_is_legacy_deduction_by_address_and_control_type` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_engine_state_without_comp_data_no_exception` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_decode_speed_info_255_conversion` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_speed_max_logic_limits` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_change_direction_toggle_tmcc1_and_tmcc2` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_duplicate_command_is_ignored_for_last_command_and_notification` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_no_change_command_records_without_notification` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_as_bytes_yields_packets_list` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_smoke_label_mapping` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_as_dict_includes_core_fields_engine` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_can_not_define_out_of_scope_field` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_train_moniker` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_train_as_bpc2_moniker` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_engine_moniker` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_train_state_as_dict_includes_consist` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_train_state_as_dict_includes_core_engine` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_train_state_rejects_non_train_scope` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_train_state_consist_component_helpers_classify_components` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_train_state_consist_helpers_return_empty_values_without_components` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_train_state_contains_engine_by_consist_tmcc_id` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_train_state_head_fetches_engine_state_from_store` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateBehavior::test_train_state_delegates_capabilities_to_head` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateRampArbitration::test_ramp_hooks_present_on_engine_state` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_nonowner_does_not_arbitrate_incoming_commands` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_self_echo_does_not_cancel` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_absolute_echo_updates_both_database_fields_but_not_local_destination` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_retired_target_command_does_not_create_ownership` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_retired_target_does_not_change_active_ramp_or_database` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_a_retarget_does_not_strand_the_step_in_flight` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_foreign_absolute_speed_cancels` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_the_reported_takeover_yields_the_road` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_a_takeover_nothing_overtook_is_not_re_asserted` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_a_suppressed_duplicate_still_reaches_the_ramp` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_our_own_echo_arriving_twice_does_not_cancel` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_a_duplicate_is_still_suppressed` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_a_duplicate_trim_is_not_absorbed_twice` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_foreign_rpm_absorbs_without_cancelling` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_foreign_labor_re_baselines_without_cancelling` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_pdi_speed_limit_record_never_cancels` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_database_snapshots_neither_arbitrate_nor_replace_local_destination` | 6 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals, target |
| `TestEngineStateRampArbitration::test_a_record_with_no_target_never_cancels` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_a_record_never_cancels_without_a_ramp_of_our_own` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_hard_aborts_stop_the_ramp_and_clear_is_ramping` | 7 | command, data, mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_redundant_same_direction_command_does_not_abort` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_hard_aborts_zero_the_target_speed` | 7 | command, data, mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_foreign_absolute_speed_becomes_the_new_target` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_a_speed_alias_resolves_to_its_absolute_speed` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_abort_ramp_leaves_the_speed_the_ramp_reached` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_abort_ramp_records_a_target_without_a_ramp_of_our_own` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_sync_target_speed_leaves_the_ramping_flag_alone` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_hard_aborts_return_effort_to_neutral_on_the_wire` | 9 | command, data, mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_a_direction_change_during_a_ramp_returns_effort_to_neutral` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_a_redundant_direction_command_leaves_effort_alone` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_a_foreign_throttle_command_hands_the_operators_effort_back` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_a_ramp_that_never_raised_effort_hands_nothing_back` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_a_tmcc1_hard_stop_sends_no_effort_command` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_a_direction_change_re_asserts_the_standstill_a_step_overtook` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_hard_aborts_re_assert_the_standstill` | 9 | command, data, mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_a_hard_stop_re_asserts_nothing_when_every_step_is_echoed` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_a_settling_ramp_and_an_abort_do_not_deadlock` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_ramp_to_starts_one_thread_and_then_retargets` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_takeover_during_start_cannot_be_hidden_by_late_owner_registration` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |
| `TestEngineStateRampArbitration::test_old_ramp_cleanup_does_not_clear_new_local_owner` | 1 | mock_command_dispatcher_ip, monkeypatch, no_comm_buffer, pin_process_globals |

## tests/db/test_engine_state_core.py

229 cases; 107 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestEngineStateConstruction::test_engine_state_accepts_engine_and_train_scopes` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateConstruction::test_engine_state_rejects_other_scopes` | 3 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals, scope |
| `TestEngineStateConstruction::test_a_fresh_engine_reports_nothing_known` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateConstruction::test_default_comp_data_values_drive_the_derived_properties` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateWithoutARecord::test_a_property_with_nothing_to_report_answers_nothing` | 22 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals, prop |
| `TestEngineStateWithoutARecord::test_a_capability_flag_with_nothing_to_report_is_not_claimed` | 11 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals, prop |
| `TestEngineStateWithoutARecord::test_is_cab1_on_empty_record_answers_false` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateWithoutARecord::test_the_labels_of_an_engine_with_no_record_read_not_available` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateWithoutARecord::test_an_engine_with_no_record_can_still_be_exported` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateWithoutARecord::test_a_train_with_no_record_reports_no_consist` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateProtocolFlavor::test_a_short_address_without_a_control_type_is_tmcc` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateProtocolFlavor::test_a_four_digit_address_is_always_legacy` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateProtocolFlavor::test_the_control_type_decides_the_flavor_of_a_short_address` | 3 | control_type, is_cab1, is_legacy, mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateProtocolFlavor::test_is_tmcc_is_the_negation_of_is_legacy` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateProtocolFlavor::test_control_type_text_marks_a_four_digit_engine` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateProtocolFlavor::test_control_type_text_leaves_an_unknown_control_type_alone` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateSpeedProperties::test_speed_is_scaled_for_a_tmcc_engine` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateSpeedProperties::test_speed_is_reported_verbatim_for_a_legacy_engine` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateSpeedProperties::test_speed_is_none_without_a_record` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateSpeedProperties::test_speed_max_resolves_the_limits` | 6 | expected, legacy, max_speed, mock_command_dispatcher_ip, monkeypatch, pin_process_globals, speed_limit |
| `TestEngineStateSpeedProperties::test_speeds_reports_the_quartet_the_ui_draws` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateSpeedProperties::test_decode_speed_info_expands_the_never_set_sentinel` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateSpeedProperties::test_rr_speed_names_the_railroad_speed_band` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateSpeedProperties::test_every_speed_step_of_a_band_reports_that_band` | 2 | command, legacy, mock_command_dispatcher_ip, monkeypatch, pin_process_globals, speeds |
| `TestEngineStateSpeedProperties::test_sync_target_speed_only_updates_the_database_target` | 6 | is_ramping, mock_command_dispatcher_ip, monkeypatch, pin_process_globals, target |
| `TestEngineStateSpeedProperties::test_the_local_ramping_flag_does_not_rewrite_database_speeds` | 2 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals, target |
| `TestEngineStateSpeedProperties::test_a_speedless_update_does_not_complete_a_local_ramp` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateSpeedProperties::test_a_speed_written_before_the_record_arrives_is_read_back_unchanged` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateSpeedProperties::test_sync_target_speed_ignores_a_missing_target_or_record` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDerivedProperties::test_fuel_and_water_are_reported_as_percentages` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDerivedProperties::test_a_missing_level_stays_missing` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDerivedProperties::test_momentum_is_converted_to_the_tmcc_scale` | 3 | mock_command_dispatcher_ip, momentum, monkeypatch, pin_process_globals, raw, text |
| `TestEngineStateDerivedProperties::test_train_brake_is_converted_to_the_tmcc_scale` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDerivedProperties::test_rpm_and_labor_share_a_single_byte` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDerivedProperties::test_a_non_rpm_engine_reports_no_rpm` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDerivedProperties::test_the_engine_type_decides_the_capability_flags` | 8 | engine_type, expected, mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDerivedProperties::test_the_type_labels_come_from_the_lionel_tables` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDerivedProperties::test_the_bluetooth_id_is_rendered_as_hex` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDerivedProperties::test_an_unset_bluetooth_id_is_none` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDerivedProperties::test_the_smoke_level_carries_a_label_and_a_caption` | 4 | label, mock_command_dispatcher_ip, monkeypatch, pin_process_globals, smoke, text |
| `TestEngineStateDerivedProperties::test_a_tmcc_engine_reports_any_smoke_level_as_on` | 3 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals, smoke |
| `TestEngineStateDerivedProperties::test_a_tmcc_engine_reports_the_base_level_of_zero_as_off` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDerivedProperties::test_an_unreported_smoke_level_has_no_caption` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDerivedProperties::test_the_train_assignment_is_read_from_the_record` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDerivedProperties::test_an_unassigned_engine_belongs_to_no_train` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDerivedProperties::test_soft_status_is_passed_through` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDirectionAndAux::test_direction_flags_follow_the_recorded_direction` | 5 | direction, is_forward, is_reverse, label, mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDirectionAndAux::test_a_toggle_without_a_known_direction_yields_nothing` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDirectionAndAux::test_a_toggle_against_the_other_syntax_yields_nothing` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDirectionAndAux::test_an_explicit_direction_passes_through_change_direction` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDirectionAndAux::test_aux1_option_one_is_what_aux_on_means` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDirectionAndAux::test_aux2_option_one_alternates_the_aux2_state` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDirectionAndAux::test_an_explicit_aux2_command_is_recorded_as_sent` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDirectionAndAux::test_is_aux1_is_answered_from_the_aux1_setting` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDirectionAndAux::test_a_first_record_initializes_the_direction` | 2 | direction, mock_command_dispatcher_ip, monkeypatch, pin_process_globals, soft_status |
| `TestEngineStateDirectionAndAux::test_a_legacy_engine_initializes_its_direction_in_its_own_syntax` | 2 | direction, mock_command_dispatcher_ip, monkeypatch, pin_process_globals, soft_status |
| `TestEngineStateDirectionAndAux::test_a_record_that_never_reached_the_soft_status_leaves_the_direction_unknown` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDirectionAndAux::test_only_the_first_record_initializes_the_direction` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateDirectionAndAux::test_a_direction_command_is_not_overruled_by_a_later_first_record` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_a_numeric_command_is_remembered` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_a_tmcc1_aux1_prefixed_numeric_becomes_a_startup` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_a_tmcc1_aux1_prefixed_five_becomes_a_shutdown` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_startup_and_shutdown_commands_are_recorded` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_a_train_brake_command_is_written_to_the_record` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_the_momentum_commands_set_their_notch` | 3 | command, expected, mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_the_legacy_momentum_command_carries_its_own_notch` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_an_rpm_command_is_written_to_the_record` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_a_labor_command_is_written_to_the_record` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_an_absolute_speed_command_moves_speed_and_target_together` | 4 | command, is_ramping, legacy, mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_a_railroad_speed_command_resolves_its_alias` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_an_incoming_target_does_not_change_database_speeds_or_local_ownership` | 6 | is_ramping, mock_command_dispatcher_ip, monkeypatch, pin_process_globals, target |
| `TestEngineStateCommandHandling::test_native_target_updates_only_target_and_preserves_local_ramp` | 24 | command, is_ramping, legacy, mock_command_dispatcher_ip, monkeypatch, packet, pin_process_globals, raw_target, scope, tmcc_target |
| `TestEngineStateCommandHandling::test_a_smoke_command_is_written_to_the_record` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_a_tmcc1_smoke_command_is_written_to_the_record` | 4 | command, data, mock_command_dispatcher_ip, monkeypatch, pin_process_globals, raw, smoke |
| `TestEngineStateCommandHandling::test_a_legacy_smoke_level_survives_a_record_with_no_control_type` | 4 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals, raw, smoke |
| `TestEngineStateCommandHandling::test_a_tmcc1_keypress_on_a_legacy_engine_records_a_level` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_a_halt_stops_the_engine_and_kills_the_accessories` | 2 | command, mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_a_direction_command_that_changes_nothing_reports_no_change` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_a_direction_command_that_changes_direction_is_an_update` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_no_command_at_all_is_ignored` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_the_train_address_and_unit_come_from_an_r4lc_command` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_a_base_memory_field_update_is_applied_to_the_record` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_an_irda_data_record_carries_the_production_year` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_a_record_leaves_a_standing_engine_bound_for_nowhere` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateCommandHandling::test_a_target_snapshot_does_not_change_local_ramp_ownership` | 8 | is_ramping, mock_command_dispatcher_ip, monkeypatch, pin_process_globals, target |
| `TestEngineStateCommandHandling::test_a_d4_mapping_records_the_four_digit_record_number` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateSerialization::test_as_dict_reports_the_state_a_client_renders` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateSerialization::test_as_csv_headers_and_row_agree` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateSerialization::test_as_bytes_carries_the_record_and_the_state_the_base_does_not_hold` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateSerialization::test_as_bytes_reports_only_the_record_for_a_pdi_sourced_engine` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateSerialization::test_repr_names_the_engine_and_its_state` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateSerialization::test_repr_says_so_when_nothing_is_known` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateSerialization::test_production_year_and_road_number` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateKnownDefects::test_a_four_digit_engine_cannot_be_serialized_before_its_record_number_arrives` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateKnownDefects::test_a_runt_first_record_spends_the_one_chance_to_read_the_direction` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestEngineStateKnownDefects::test_a_state_with_no_address_cannot_report_its_protocol_flavor` | 6 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals, prop |
| `TestEngineStateKnownDefects::test_a_state_with_no_address_cannot_say_that_it_knows_nothing` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestTrainStateCore::test_a_multi_digit_train_is_legacy_by_its_address` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestTrainStateCore::test_a_train_under_a_hundred_takes_its_flavor_from_its_record` | 4 | control_type, is_legacy, mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestTrainStateCore::test_a_legacy_command_makes_a_train_legacy` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestTrainStateCore::test_a_train_rejects_any_other_scope` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestTrainStateCore::test_a_train_without_a_head_engine_reports_no_capabilities` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestTrainStateCore::test_a_train_reports_its_transformer_type_from_its_own_record` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestTrainStateCore::test_a_train_without_a_consist_is_exported_with_no_components` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestTrainStateCore::test_a_train_as_dict_carries_its_consist` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestTrainStateCore::test_a_speed_written_to_a_train_is_read_back_unchanged` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |
| `TestTrainStateCore::test_a_train_whose_record_says_legacy_reads_its_speed_back_unchanged` | 1 | mock_command_dispatcher_ip, monkeypatch, pin_process_globals |

## tests/db/test_irda_state.py

90 cases; 29 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestIrdaStateBasics::test_defaults_and_registration` | 1 | mock_command_dispatcher_ip, sensor |
| `TestIrdaStateBasics::test_invalid_scope` | 14 | mock_command_dispatcher_ip, scope |
| `TestIrdaStateBasics::test_configuration_updates_sequence_and_filters` | 10 | mock_command_dispatcher_ip, sensor, sequence |
| `TestIrdaStateBasics::test_repr_any_engine_filters` | 3 | loco_id, mock_command_dispatcher_ip, sensor |
| `TestIrdaStateBasics::test_sequence_update_preserves_configuration_filters` | 1 | mock_command_dispatcher_ip, sensor |
| `TestIrdaStateBasics::test_outgoing_commands_do_not_change_sequence` | 2 | mock_command_dispatcher_ip, pdi_command, sensor |
| `TestIrdaStateBasics::test_unrelated_command_is_ignored` | 1 | mock_command_dispatcher_ip, sensor |
| `TestIrdaStateBasics::test_other_received_action_is_accepted_without_sequence_change` | 1 | mock_command_dispatcher_ip, sensor |
| `TestIrdaStateBasics::test_data_updates_direction_and_identity` | 3 | direction, expected, io, mock_command_dispatcher_ip, monkeypatch, sensor |
| `TestIrdaStateBasics::test_engine_and_train_classification` | 4 | engine_id, io, mock_command_dispatcher_ip, monkeypatch, sensor, train_id |
| `TestIrdaStateBasics::test_train_disappearing_after_packet_parse_is_cleared` | 1 | io, mock_command_dispatcher_ip, monkeypatch, sensor |
| `TestIrdaStateBasics::test_serialization_preserves_lcs_packets_and_only_latest_data` | 1 | io, mock_command_dispatcher_ip, monkeypatch, sensor |
| `TestIrdaStateIdLookup::test_bluetooth_lookup_takes_precedence_over_engine_id_and_road_number` | 3 | engine_id, io, mock_command_dispatcher_ip, monkeypatch |
| `TestIrdaStateIdLookup::test_default_id_uses_road_number_fallback` | 6 | expected, found, io, mock_command_dispatcher_ip, monkeypatch, number, scope |
| `TestIrdaStateIdLookup::test_nonnumeric_road_number_keeps_unresolved_default` | 5 | io, mock_command_dispatcher_ip, monkeypatch, number |
| `TestIrdaStateIdLookup::test_nondefault_id_does_not_use_road_number` | 3 | engine_id, io, mock_command_dispatcher_ip, monkeypatch |
| `TestIrdaStateIdLookup::test_zero_bluetooth_id_skips_state_lookup` | 1 | io, mock_command_dispatcher_ip, monkeypatch |
| `TestIrdaStateIdLookup::test_packet_without_bluetooth_field_preserves_engine_id` | 1 | io, mock_command_dispatcher_ip, monkeypatch |
| `TestIrdaStateIdLookup::test_non_irda_command_uses_ids_without_bluetooth_lookup` | 1 | io, mock_command_dispatcher_ip, monkeypatch |
| `TestIrdaStateIdLookup::test_non_data_action_does_not_lookup_bluetooth` | 1 | io, mock_command_dispatcher_ip, monkeypatch |
| `TestIrdaStateIdLookup::test_real_bluetooth_index_resolves_default_id_to_four_digit_engine` | 2 | addresses, mock_command_dispatcher_ip, monkeypatch |
| `TestIrdaStateSpeedControl::test_bluetooth_match_arriving_after_parse_resolves_speed_target` | 1 | caplog, io, mock_command_dispatcher_ip, monkeypatch, sensor |
| `TestIrdaStateSpeedControl::test_speed_and_propagation_target_resolved_ids` | 8 | direction, io, mock_command_dispatcher_ip, monkeypatch, sensor, sequence, speed, train_id |
| `TestIrdaStateSpeedControl::test_other_sequences_do_not_send_or_propagate` | 9 | io, mock_command_dispatcher_ip, monkeypatch, sensor, sequence |
| `TestIrdaStateSpeedControl::test_client_or_unresolved_default_ids_suppress_speed_and_propagation` | 3 | engine_id, io, mock_command_dispatcher_ip, monkeypatch, sensor, server, train_id |
| `TestIrdaStateSpeedControl::test_unknown_direction_does_not_send_speed_but_propagates` | 1 | io, mock_command_dispatcher_ip, monkeypatch, sensor |
| `TestIrdaStateSpeedControl::test_missing_speed_target_does_not_send` | 1 | io, mock_command_dispatcher_ip, monkeypatch, sensor |
| `TestIrdaStateSpeedControl::test_missing_engine_id_does_not_propagate` | 1 | io, mock_command_dispatcher_ip, monkeypatch, sensor |
| `TestIrdaStateSpeedControl::test_propagation_exception_restores_request_identity` | 1 | io, mock_command_dispatcher_ip, monkeypatch, sensor |

## tests/db/test_lcs_state_serialization.py

25 cases; 6 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_accessory_state_as_bytes_includes_received_lcs_config_firmware_and_info_packets` | 1 | mock_command_dispatcher_ip |
| `test_switch_state_as_bytes_includes_received_lcs_config_firmware_and_info_packets` | 1 | mock_command_dispatcher_ip |
| `test_train_state_as_bytes_includes_received_lcs_config_firmware_and_info_packets` | 1 | mock_command_dispatcher_ip, monkeypatch |
| `test_lcs_as_bytes_normalizes_inherited_packets` | 8 | include_lcs, inherited, mock_command_dispatcher_ip, monkeypatch |
| `test_switch_as_bytes_normalizes_inherited_packets` | 12 | inherited, mock_command_dispatcher_ip, monkeypatch, position |
| `test_engine_and_train_serialization_retains_packet_lists` | 2 | mock_command_dispatcher_ip, scope, state_class |

## tests/db/test_prod_info.py

12 cases; 12 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_get_info_uses_configured_timeouts` | 1 | _xunit_setup_function_fixture_tests.db.test_prod_info, mock_command_dispatcher_ip, monkeypatch |
| `test_by_btid_caches_successful_lookup` | 1 | _xunit_setup_function_fixture_tests.db.test_prod_info, mock_command_dispatcher_ip, monkeypatch |
| `test_by_btid_failure_is_negative_cached` | 1 | _xunit_setup_function_fixture_tests.db.test_prod_info, mock_command_dispatcher_ip, monkeypatch |
| `test_by_btid_missing_configuration_is_negative_cached` | 1 | _xunit_setup_function_fixture_tests.db.test_prod_info, mock_command_dispatcher_ip, monkeypatch |
| `test_get_info_reads_from_cache_file` | 1 | _xunit_setup_function_fixture_tests.db.test_prod_info, mock_command_dispatcher_ip, monkeypatch, tmp_path, tmp_path_factory |
| `test_get_info_writes_to_cache_file` | 1 | _xunit_setup_function_fixture_tests.db.test_prod_info, mock_command_dispatcher_ip, monkeypatch, tmp_path, tmp_path_factory |
| `test_get_info_does_not_cache_when_info_cache_dir_is_empty` | 1 | _xunit_setup_function_fixture_tests.db.test_prod_info, mock_command_dispatcher_ip, monkeypatch, tmp_path, tmp_path_factory |
| `test_image_content_reads_from_cache_file` | 1 | _xunit_setup_function_fixture_tests.db.test_prod_info, mock_command_dispatcher_ip, monkeypatch, tmp_path, tmp_path_factory |
| `test_image_content_writes_to_cache_file` | 1 | _xunit_setup_function_fixture_tests.db.test_prod_info, mock_command_dispatcher_ip, monkeypatch, tmp_path, tmp_path_factory |
| `test_image_content_does_not_cache_when_image_cache_dir_is_empty` | 1 | _xunit_setup_function_fixture_tests.db.test_prod_info, mock_command_dispatcher_ip, monkeypatch, tmp_path, tmp_path_factory |
| `test_no_file_caching_when_both_cache_dirs_are_empty` | 1 | _xunit_setup_function_fixture_tests.db.test_prod_info, mock_command_dispatcher_ip, monkeypatch, tmp_path, tmp_path_factory |
| `test_clear_caches_removes_cache_files_and_clears_memory` | 1 | _xunit_setup_function_fixture_tests.db.test_prod_info, mock_command_dispatcher_ip, monkeypatch, tmp_path, tmp_path_factory |

## tests/db/test_ramp_claim_state.py

73 cases; 17 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_first_claim_wins_until_matching_release` | 1 | mock_command_dispatcher_ip, monkeypatch, state |
| `test_earlier_timestamp_wins_even_when_received_last` | 2 | mock_command_dispatcher_ip, monkeypatch, reverse, state |
| `test_equal_millisecond_claims_use_identity_tiebreaker` | 2 | mock_command_dispatcher_ip, monkeypatch, reverse, state |
| `test_reused_endpoint_and_id_do_not_make_old_release_match_new_claim` | 1 | mock_command_dispatcher_ip, monkeypatch, state |
| `test_remote_claim_blocks_ramp_start_without_replacing_owner` | 1 | mock_command_dispatcher_ip, monkeypatch, state |
| `test_claim_is_metadata_not_remote_ramp_or_speed_change` | 1 | mock_command_dispatcher_ip, monkeypatch, state |
| `test_local_claim_keeps_own_throttle_enabled` | 1 | mock_command_dispatcher_ip, monkeypatch, state |
| `test_delayed_release_and_refresh_cannot_erase_new_owner` | 1 | mock_command_dispatcher_ip, monkeypatch, state |
| `test_rejected_claim_cannot_reappear_after_owner_completes` | 1 | mock_command_dispatcher_ip, monkeypatch, state |
| `test_release_before_announcement_does_not_create_abandoned_owner` | 1 | mock_command_dispatcher_ip, monkeypatch, state |
| `test_matching_release_unlocks_without_residual_endpoint` | 1 | mock_command_dispatcher_ip, monkeypatch, state |
| `test_local_ramp_lifecycle_notifies_watchers_without_speed_updates` | 1 | mock_command_dispatcher_ip, monkeypatch, state |
| `test_lease_refresh_and_expiration_are_bounded` | 1 | mock_command_dispatcher_ip, monkeypatch, state |
| `test_current_state_sync_contains_only_active_claim` | 2 | mock_command_dispatcher_ip, monkeypatch, released, state |
| `test_safety_overrides_claims_and_duplicate_suppression` | 54 | command, data, mock_command_dispatcher_ip, monkeypatch, pending, state |
| `test_nonowner_speed_updates_never_create_peer_service` | 1 | mock_command_dispatcher_ip, monkeypatch, state |
| `test_foreign_claim_cannot_stop_local_owner_or_change_database` | 1 | mock_command_dispatcher_ip, monkeypatch, state |

## tests/db/test_startup_state.py

9 cases; 9 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_config_registration_enqueues_followups_once` | 1 | build_component_store, mock_command_dispatcher_ip, monkeypatch, no_thread_start |
| `test_base_memory_triggers_next_query` | 1 | build_component_store, mock_command_dispatcher_ip, monkeypatch, no_thread_start |
| `test_base_memory_triggers_sync_complete_and_next_query` | 1 | build_component_store, mock_command_dispatcher_ip, monkeypatch, no_thread_start |
| `test_base_memory_requests_created_for_all_scopes` | 1 | build_component_store, mock_command_dispatcher_ip, monkeypatch, no_thread_start |
| `test_d4_count_requests_first_record` | 1 | build_component_store, mock_command_dispatcher_ip, monkeypatch, no_thread_start |
| `test_event_set_when_waiting_for_empty` | 1 | build_component_store, mock_command_dispatcher_ip, monkeypatch, no_thread_start |
| `test_run_enqueues_base_memory_requests_for_all_scopes` | 1 | build_component_store, mock_command_dispatcher_ip, monkeypatch, no_thread_start |
| `test_run_skips_amc2_sync_when_listener_has_no_dispatcher` | 1 | build_component_store, mock_command_dispatcher_ip, monkeypatch, no_thread_start |
| `test_base_memory_id1_responses_trigger_id2_requests_per_scope` | 1 | build_component_store, mock_command_dispatcher_ip, monkeypatch, no_thread_start |

## tests/db/test_state_watcher.py

4 cases; 4 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestStateWatcher::test_watched_property_and_action_delegate` | 1 | mock_command_dispatcher_ip |
| `TestStateWatcher::test_triggers_action_on_accessory_update` | 1 | mock_command_dispatcher_ip |
| `TestStateWatcher::test_multiple_updates_collapse_to_calls_and_shutdown_stops_processing` | 1 | mock_command_dispatcher_ip |
| `TestStateWatcher::test_shutdown_is_idempotent_and_notifier_unblocks` | 1 | mock_command_dispatcher_ip |

## tests/gpio/i2c/test_i2c.py

4 cases; 4 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestI2c::test_i2c_init` | 1 | _xunit_setup_method_fixture_TestI2c |
| `TestI2c::test_write_read_data` | 1 | _xunit_setup_method_fixture_TestI2c |
| `TestI2c::test_read` | 1 | _xunit_setup_method_fixture_TestI2c |
| `TestI2c::test_scan` | 1 | _xunit_setup_method_fixture_TestI2c |

## tests/gpio/i2c/test_mcp23017.py

11 cases; 11 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestMCP23017::test_digital_write` | 1 | _unittest_setUpClass_fixture_TestMCP23017 |
| `TestMCP23017::test_get_offset_pin_pair` | 1 | _unittest_setUpClass_fixture_TestMCP23017 |
| `TestMCP23017::test_get_offset_pin_pair_type_error` | 1 | _unittest_setUpClass_fixture_TestMCP23017 |
| `TestMCP23017::test_interrupt_mirror` | 1 | _unittest_setUpClass_fixture_TestMCP23017 |
| `TestMCP23017::test_mcp23017_init` | 1 | _unittest_setUpClass_fixture_TestMCP23017 |
| `TestMCP23017::test_pin_mode` | 1 | _unittest_setUpClass_fixture_TestMCP23017 |
| `TestMCP23017::test_read_interrupt_captures` | 1 | _unittest_setUpClass_fixture_TestMCP23017 |
| `TestMCP23017::test_set_all_input` | 1 | _unittest_setUpClass_fixture_TestMCP23017 |
| `TestMCP23017::test_set_all_interrupt` | 1 | _unittest_setUpClass_fixture_TestMCP23017 |
| `TestMCP23017::test_set_all_output` | 1 | _unittest_setUpClass_fixture_TestMCP23017 |
| `TestMCP23017::test_set_interrupt` | 1 | _unittest_setUpClass_fixture_TestMCP23017 |

## tests/gpio/test_engine_status.py

4 cases; 4 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_initial_sync_incomplete_shows_synchronizing_and_sets_watcher` | 1 | monkeypatch, patched_engine_status |
| `test_on_sync_sets_synchronized_and_updates_display_not_found` | 1 | monkeypatch, patched_engine_status |
| `test_update_engine_sets_state_and_clears_display_and_starts_watcher` | 1 | monkeypatch, patched_engine_status |
| `test_update_display_with_state_populates_rows_and_cursor` | 1 | monkeypatch, patched_engine_status |

## tests/gpio/test_gpio_device.py

1 cases; 1 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestGPIODevice::test_cannot_instantiate_abstract_class` | 1 | _unittest_setUpClass_fixture_TestGPIODevice, _unittest_setup_method_fixture_TestGPIODevice |

## tests/gpio/utils/test_text_buffer.py

20 cases; 20 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestTextBuffer::test_initialization` | 1 |  |
| `TestTextBuffer::test_repr_empty` | 1 |  |
| `TestTextBuffer::test_set_and_get_item` | 1 |  |
| `TestTextBuffer::test_set_item_out_of_bounds` | 1 |  |
| `TestTextBuffer::test_delete_item` | 1 |  |
| `TestTextBuffer::test_insert_item` | 1 |  |
| `TestTextBuffer::test_insert_out_of_bounds` | 1 |  |
| `TestTextBuffer::test_reverse_buffer` | 1 |  |
| `TestTextBuffer::test_add_row` | 1 |  |
| `TestTextBuffer::test_add_row_exceeds_limit` | 1 |  |
| `TestTextBuffer::test_contains` | 1 |  |
| `TestTextBuffer::test_count` | 1 |  |
| `TestTextBuffer::test_clear_buffer` | 1 |  |
| `TestTextBuffer::test_auto_update_property` | 1 |  |
| `TestTextBuffer::test_cursor_pos_setting` | 1 |  |
| `TestTextBuffer::test_cursor_pos_invalid` | 1 |  |
| `TestTextBuffer::test_changed_rows` | 1 |  |
| `TestTextBuffer::test_write_char` | 1 |  |
| `TestTextBuffer::test_write_string` | 1 |  |
| `TestTextBuffer::test_write_out_of_bounds` | 1 |  |

## tests/gui/accessory/test_accessories_gui_catalog.py

5 cases; 5 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_register_duplicate_key_rejected` | 1 |  |
| `test_resolve_exact_match_and_normalization` | 1 |  |
| `test_resolve_substring_match_prefers_first_insert_order` | 1 |  |
| `test_resolve_invalid_raises` | 1 |  |
| `test_load_class_lazy_import` | 1 |  |

## tests/gui/accessory/test_accessory_gui.py

10 cases; 10 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_configured_set_prefers_current_directory_over_cache` | 1 | _isolate, _patch_registry_and_catalog, monkeypatch, tmp_path, tmp_path_factory |
| `test_configured_set_falls_back_to_cache_directory` | 1 | _isolate, _patch_registry_and_catalog, monkeypatch, tmp_path, tmp_path_factory |
| `test_configured_set_missing_cache_directory_is_empty` | 1 | _isolate, _patch_registry_and_catalog, monkeypatch, tmp_path, tmp_path_factory |
| `test_loads_config_and_disambiguates_labels` | 1 | _isolate, _patch_registry_and_catalog, monkeypatch, tmp_path, tmp_path_factory |
| `test_uses_display_name_override` | 1 | _isolate, _patch_registry_and_catalog, monkeypatch, tmp_path, tmp_path_factory |
| `test_missing_gui_raises` | 1 | _isolate, _patch_registry_and_catalog, monkeypatch, tmp_path, tmp_path_factory |
| `test_empty_config_raises` | 1 | _isolate, _patch_registry_and_catalog, monkeypatch, tmp_path, tmp_path_factory |
| `test_cycle_gui_updates_selection_and_sets_event` | 1 | _isolate, _patch_registry_and_catalog, monkeypatch, tmp_path, tmp_path_factory |
| `test_cycle_gui_ignores_unknown_label` | 1 | _isolate, _patch_registry_and_catalog, monkeypatch, tmp_path, tmp_path_factory |
| `test_create_gui_sets_aggregator_and_menu_label` | 1 | _isolate, _patch_registry_and_catalog, monkeypatch, tmp_path, tmp_path_factory |

## tests/gui/accessory/test_accessory_registry.py

7 cases; 7 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_register_and_duplicate_type_rejected` | 1 | reg |
| `test_default_variant_explicit_default` | 1 | reg |
| `test_default_variant_fallback_first` | 1 | reg |
| `test_resolve_variant_by_key_display_title_alias` | 1 | reg |
| `test_resolve_variant_substring_match` | 1 | reg |
| `test_get_definition_bundles_operation_images_override` | 1 | reg |
| `test_operation_label_override` | 1 | reg |

## tests/gui/accessory/test_station_gui.py

1 cases; 1 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_build_accessory_controls_clears_stale_button_references_before_remount` | 1 |  |

## tests/gui/controller/test_accessory_bindings.py

168 cases; 79 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_the_module_is_importable_without_a_display` | 1 |  |
| `test_the_long_press_action_names_agree_with_the_router` | 1 |  |
| `test_every_default_binding_names_a_known_verb` | 1 |  |
| `test_every_context_is_named_by_the_key_it_is_filed_under` | 1 |  |
| `test_every_inherited_context_exists` | 1 |  |
| `test_the_switch_context_throws_each_control_the_way_the_panel_does` | 10 | action, verb |
| `test_the_route_context_fires_from_everything_but_the_horn` | 5 | action |
| `test_the_route_context_claims_the_horn_and_sends_nothing` | 1 |  |
| `test_the_two_panel_types_claim_the_same_controls` | 1 |  |
| `test_only_the_sticks_latch` | 1 |  |
| `test_a_switch_ignores_the_sign_and_a_route_does_not` | 1 |  |
| `test_both_contexts_hand_the_face_buttons_back_to_the_catalog` | 1 |  |
| `test_neither_context_claims_what_it_has_not_bound` | 1 |  |
| `test_an_empty_chain_resolves_nothing` | 1 |  |
| `test_an_unknown_context_name_is_skipped_rather_than_raised` | 1 |  |
| `test_the_most_specific_link_wins_where_two_define_the_same_action` | 1 |  |
| `test_an_action_only_the_outer_link_defines_falls_through_to_it` | 1 |  |
| `test_an_explicit_none_unbinds_without_reaching_the_link_it_inherits` | 1 |  |
| `test_a_claiming_base_swallows_anything_the_chain_leaves_unbound` | 1 |  |
| `test_an_explicitly_listed_chain_is_walked_in_the_order_given` | 1 |  |
| `test_a_cycle_in_the_inheritance_terminates` | 1 |  |
| `test_a_silent_profile_leaves_the_defaults_exactly_as_they_were` | 1 |  |
| `test_an_override_replaces_one_entry_and_leaves_its_neighbours_alone` | 1 |  |
| `test_null_unbinds_an_entry_without_removing_the_claim_below_it` | 1 |  |
| `test_a_profile_may_add_a_whole_context_and_chain_it` | 1 |  |
| `test_a_context_set_to_null_is_dropped_entirely` | 1 |  |
| `test_the_flags_are_overridable_and_default_to_what_was_there` | 1 |  |
| `test_a_malformed_entry_is_skipped_rather_than_raised` | 11 | raw |
| `test_an_unknown_action_is_skipped_when_the_caller_says_which_are_known` | 1 |  |
| `test_an_unknown_axis_variant_is_skipped_when_the_caller_says_which_are_known` | 1 |  |
| `test_a_protected_action_cannot_be_rebound_or_swallowed` | 1 |  |
| `test_a_command_list_survives_as_a_tuple` | 1 |  |
| `test_the_generic_accessory_context_chains_over_the_base` | 1 |  |
| `test_the_generic_panel_binds_the_keys_it_shows` | 6 | action, command, verb |
| `test_the_generic_stick_toggle_is_latched_and_sign_blind` | 1 |  |
| `test_an_axis_variant_is_resolved_before_the_plain_action` | 2 | value, verb |
| `test_an_axis_without_variants_falls_back_to_the_plain_action` | 2 | value |
| `test_a_one_sided_axis_override_unbinds_only_that_sign` | 1 |  |
| `test_axis_variant_names_are_the_sign_pair_for_each_supported_axis` | 1 |  |
| `test_the_generic_dpad_entries_repeat_while_held` | 1 |  |
| `test_only_the_accessory_throttle_is_analog` | 1 |  |
| `test_the_generic_panel_lets_go_of_the_shoulder_buttons_for_the_catalog` | 1 |  |
| `test_an_unbound_generic_action_is_claimed_by_the_base` | 1 |  |
| `test_the_power_district_pair_is_reached_from_both_panels` | 16 | action, chain, verb |
| `test_the_power_district_stick_pair_is_reached_from_both_panels` | 2 | value, verb |
| `test_the_asc2_context_states_only_its_difference` | 1 |  |
| `test_the_asc2_momentary_entry_carries_both_phases` | 2 | action |
| `test_the_generic_aux_bindings_do_not_reach_the_power_district_panels` | 8 | action, panel |
| `test_the_vertical_stick_holds_the_asc2_output_and_is_sign_blind` | 1 |  |
| `test_the_asc2_stick_is_bound_as_the_plain_action_rather_than_the_sign_pair` | 1 |  |
| `test_the_vertical_stick_stays_unbound_on_a_bare_power_district` | 1 |  |
| `test_the_dpad_steps_the_sequence_group_the_way_it_reads_on_screen` | 2 | action, delta |
| `test_the_sequence_step_does_not_repeat_while_the_dpad_is_held` | 2 | action |
| `test_the_sensor_track_context_binds_the_dpad_and_the_two_keys_that_choose` | 1 |  |
| `test_the_sensor_track_panel_claims_its_other_controls_and_sends_none_of_them` | 6 | action |
| `test_the_sensor_track_context_states_its_own_catalog_carve_out` | 1 |  |
| `test_the_sensor_track_panel_is_the_only_new_chain` | 1 |  |
| `test_a_held_axis_counts_as_an_axis_for_the_derived_name_sets` | 1 |  |
| `test_a_latched_axis_is_still_an_axis` | 1 |  |
| `test_each_default_binding_claims_at_most_one_axis_mode` | 1 |  |
| `test_a_binding_claiming_two_axis_modes_is_skipped_rather_than_resolved_arbitrarily` | 3 | raw |
| `test_a_profile_may_bind_a_held_axis_of_its_own` | 1 |  |
| `test_no_accessory_panel_claims_the_controls_it_is_left_by` | 4 | action, panel |
| `test_no_accessory_panel_claims_x_while_a_popup_is_up` | 4 | action, panel |
| `test_x_is_claimed_again_once_there_is_no_popup_to_close` | 3 | action, panel |
| `test_the_sensor_track_panel_gives_x_a_meaning_of_its_own_with_no_popup_up` | 1 | action |
| `test_the_never_claimed_actions_are_ones_the_profile_can_bind` | 2 | action |
| `test_the_carve_out_sets_name_menu_and_x_on_their_own_terms` | 1 |  |
| `test_an_explicit_binding_wins_over_the_carve_out` | 1 |  |
| `test_an_explicit_claim_of_menu_is_honoured_too` | 1 |  |
| `test_an_explicit_unbind_leaves_the_carve_out_standing` | 1 |  |
| `test_the_popup_gated_carve_out_wins_over_an_explicit_binding_of_x` | 1 |  |
| `test_an_explicit_unbind_of_x_leaves_the_popup_gated_carve_out_standing` | 1 |  |
| `test_exactly_the_carve_out_falls_through_and_nothing_else` | 8 | panel, popup_visible |
| `test_every_accessory_context_hands_the_whole_dpad_to_an_open_catalog` | 5 | context |
| `test_the_face_buttons_still_yield_alongside_the_dpad` | 5 | context |
| `test_the_switch_and_route_contexts_are_left_alone` | 2 | context |
| `test_the_dpad_action_names_agree_with_the_router` | 1 |  |
| `test_neither_power_district_context_chains_through_the_generic_one` | 2 | context |

## tests/gui/controller/test_admin_panel_layout.py

58 cases; 48 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_compact_titlebox_has_bounded_height_and_equal_control_columns` | 1 | monkeypatch |
| `test_portrait_titlebox_still_asserts_the_panel_width` | 1 | monkeypatch |
| `test_the_restore_pass_keeps_each_controls_own_padding` | 1 |  |
| `test_compact_admin_action_rows_are_fixed_to_shared_control_height` | 1 | monkeypatch |
| `test_compact_sections_fit_title_and_all_admin_actions` | 1 |  |
| `test_scope_group_spans_compact_columns_without_changing_portrait_grid` | 1 |  |
| `test_popup_title_includes_runtime_version` | 1 |  |
| `test_flatpak_title_displays_one_release_version` | 6 | compact, expected, tag |
| `test_flatpak_server_title_preserves_role` | 1 |  |
| `test_portrait_database_height_retains_button_size` | 1 |  |
| `test_admin_footer_keeps_default_spacing_unless_the_host_requests_less` | 2 | compact |
| `test_database_section_fits_its_controls_without_shrinking_the_pi_layout` | 4 | button_size, compact, expected_height, required_height |
| `test_portrait_titlebox_retains_natural_height_and_existing_grid` | 1 | monkeypatch |
| `test_compact_admin_actions_use_three_consecutive_rows` | 1 |  |
| `test_compact_controls_have_uniform_padding` | 1 |  |
| `test_compact_image_backed_controls_fill_shared_row` | 1 |  |
| `test_portrait_controls_retain_native_geometry` | 1 |  |
| `test_steam_deck_disables_the_os_upgrade_button` | 1 | monkeypatch |
| `test_other_platforms_keep_the_os_upgrade_button` | 1 | monkeypatch |
| `test_admin_panel_is_an_overlay_panel` | 1 |  |
| `test_landscape_admin_panel_offers_show_controls` | 1 |  |
| `test_portrait_admin_panel_has_no_footer_at_all` | 1 |  |
| `test_footer_button_is_left_aligned_so_close_lands_to_its_right` | 1 | monkeypatch |
| `test_footer_gap_is_a_spacer_widget_not_pack_padding` | 1 | monkeypatch |
| `test_show_controls_closes_the_admin_panel_first` | 1 | monkeypatch |
| `test_unchanged_wifi_visibility_does_not_repack` | 1 | monkeypatch |
| `test_changed_wifi_visibility_still_updates` | 1 | monkeypatch |
| `test_wifi_refresh_is_skipped_while_a_button_is_held` | 1 | monkeypatch |
| `test_wifi_refresh_resumes_once_the_hold_ends` | 1 | monkeypatch |
| `test_hold_in_progress_reports_any_held_button` | 1 |  |
| `test_the_wifi_query_runs_off_the_tk_thread` | 1 | monkeypatch |
| `test_only_one_wifi_query_runs_at_a_time` | 1 |  |
| `test_display_leaves_widgets_alone_until_the_first_query_lands` | 1 | monkeypatch |
| `test_a_failing_query_keeps_the_last_good_value_and_clears_the_flag` | 1 | monkeypatch |
| `test_touch_recovery_is_enabled_on_the_steam_deck` | 1 | monkeypatch |
| `test_the_pi_gets_no_touch_recovery` | 1 | monkeypatch |
| `test_drag_off_cancel_applies_to_both_platforms` | 1 | monkeypatch |
| `test_a_two_option_group_is_regridded_onto_the_checkbox_columns` | 1 |  |
| `test_a_portrait_group_is_regridded_but_not_stretched` | 1 |  |
| `test_a_group_that_is_not_two_up_keeps_guizeros_own_packing` | 1 |  |
| `test_the_scope_radios_are_the_same_width_as_the_logging_checkboxes` | 1 |  |
| `test_compact_grid_options_are_restored_after_creation_wipes_them` | 1 |  |
| `test_portrait_records_no_compact_controls_to_restore` | 1 |  |
| `test_no_titlebox_is_given_a_height_without_a_width` | 1 | monkeypatch |
| `test_two_control_columns_and_their_spacer_fit_inside_a_section` | 1 |  |
| `test_the_column_floor_leaves_the_columns_a_usable_share` | 1 |  |
| `test_the_compact_admin_box_carries_no_chrome_of_its_own` | 1 | monkeypatch |
| `test_managed_update_button_cannot_be_held_or_triggered_by_controller` | 2 | managed, monkeypatch |

## tests/gui/controller/test_bell_horn_panel.py

8 cases; 8 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_neither_device_uses_the_emoji_pause_codepoint` | 1 | monkeypatch |
| `test_both_rows_keep_their_other_keys_in_either_mode` | 1 | monkeypatch |
| `test_the_glyph_is_monochrome_by_construction` | 1 |  |
| `test_the_glyph_is_wide_enough_to_justify_naming_its_size` | 1 |  |
| `test_every_glyph_label_still_gets_the_large_font` | 1 |  |
| `test_the_play_pause_key_names_a_smaller_size_on_both_devices` | 1 | monkeypatch |
| `test_no_other_key_gets_its_size_named_in_either_mode` | 1 | monkeypatch |
| `test_the_glyph_is_the_same_on_both_devices` | 1 | monkeypatch |

## tests/gui/controller/test_control_labels.py

60 cases; 43 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_engine_commands_are_named_by_their_enum` | 6 | action, expected |
| `test_awkward_enum_names_are_overridden` | 3 | action, expected |
| `test_app_actions_have_labels_of_their_own` | 1 |  |
| `test_the_catalog_row_says_which_pane_it_opens_and_says_it_as_a_note` | 1 |  |
| `test_an_unknown_action_is_still_readable` | 1 |  |
| `test_command_label_returns_none_for_a_non_command` | 1 |  |
| `test_button_labels_including_the_unknown_fallback` | 7 | expected, index |
| `test_axis_and_touchpad_fallbacks` | 1 |  |
| `test_chords_render_modifier_first` | 1 |  |
| `test_chord_with_unknown_buttons_sorts_last_by_index` | 1 |  |
| `test_summary_of_the_bundled_profile_names_the_deck_buttons` | 1 |  |
| `test_the_system_buttons_read_with_what_works_anywhere` | 1 |  |
| `test_summary_marks_pane_scoped_bindings` | 1 |  |
| `test_sticks_list_throttle_before_direction_per_pane` | 1 |  |
| `test_axis_inversion_is_not_surfaced` | 1 |  |
| `test_the_throttle_note_says_when_a_gesture_reaches_the_engine` | 1 |  |
| `test_the_throttle_note_is_the_bundled_profiles_own_commit_policy` | 1 |  |
| `test_a_profile_that_selects_a_commit_policy_reads_its_own_note` | 3 | policy |
| `test_a_profile_that_omits_the_commit_policy_reads_the_default_it_falls_back_to` | 1 |  |
| `test_every_commit_policy_has_a_note_of_its_own` | 1 |  |
| `test_a_note_that_needs_a_profile_is_empty_without_one` | 1 |  |
| `test_triggers_describe_their_hold_behaviour` | 1 |  |
| `test_chords_are_grouped_by_where_they_work` | 1 |  |
| `test_a_pane_scoped_chord_is_not_filed_under_anywhere` | 1 |  |
| `test_the_triggers_are_listed_with_the_buttons` | 1 |  |
| `test_summary_flags_repeating_buttons` | 1 |  |
| `test_the_switch_panel_remap_is_listed` | 1 |  |
| `test_the_switch_row_names_the_buttons_the_router_claims` | 1 |  |
| `test_the_switch_stick_rows_lead_with_the_axis_that_throws_thru` | 2 | row, side, target |
| `test_the_route_panel_remap_is_listed` | 1 |  |
| `test_the_route_row_names_the_one_face_button_that_fires` | 1 |  |
| `test_the_route_rows_name_only_the_deflections_that_fire` | 1 |  |
| `test_the_route_section_follows_the_switch_section` | 1 |  |
| `test_the_panel_remaps_name_their_sticks_as_the_joysticks_section_does` | 2 | title |
| `test_context_sections_are_titled_by_the_panel_they_apply_to` | 1 |  |
| `test_the_catalog_lists_both_ways_out_of_it` | 1 |  |
| `test_the_lcs_config_panel_remap_is_written_up` | 1 |  |
| `test_the_lcs_config_rows_name_every_key_the_router_claims` | 1 |  |
| `test_the_lcs_config_stick_and_pad_are_named_as_scrolling_the_page` | 1 |  |
| `test_the_lcs_config_rows_are_held_off_the_screen_for_now` | 1 |  |
| `test_fixed_sections_are_marked_as_such` | 1 |  |
| `test_summary_follows_a_custom_profile` | 1 |  |
| `test_empty_sections_are_dropped` | 1 |  |

## tests/gui/controller/test_controller_view_throttle.py

80 cases; 43 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_the_lever_starts_from_the_speed_the_engine_says_it_is_headed_for` | 1 | monkeypatch |
| `test_the_lever_falls_back_to_the_speed_when_no_target_is_announced` | 1 | monkeypatch |
| `test_holding_the_lever_up_stops_at_the_engines_top_speed` | 1 | monkeypatch |
| `test_holding_the_lever_down_stops_at_a_stand_and_never_goes_below` | 1 | monkeypatch |
| `test_a_speed_limit_arriving_mid_gesture_pulls_the_lever_back_down` | 1 | monkeypatch |
| `test_a_cab_1_engine_has_no_lever_to_move` | 1 | monkeypatch |
| `test_no_engine_selected_leaves_the_lever_unseeded` | 1 | monkeypatch |
| `test_committing_sends_one_command_for_where_the_lever_rests` | 1 | monkeypatch |
| `test_committing_an_explicit_speed_leaves_the_lever_where_it_was` | 1 | monkeypatch |
| `test_committing_clamps_to_the_engines_top_speed` | 1 | monkeypatch |
| `test_committing_with_no_lever_held_sends_nothing` | 1 | monkeypatch |
| `test_clearing_the_lever_sends_nothing` | 1 | monkeypatch |
| `test_a_state_refresh_leaves_the_slider_on_the_lever` | 1 | monkeypatch |
| `test_a_state_refresh_moves_the_slider_once_the_lever_is_let_go` | 1 | monkeypatch |
| `test_the_handle_stays_on_the_committed_speed_while_the_engine_is_still_catching_up` | 1 | monkeypatch |
| `test_the_handle_follows_the_engine_again_once_it_announces_the_committed_speed` | 1 | monkeypatch |
| `test_the_handle_stops_waiting_for_a_command_that_never_lands` | 1 | monkeypatch |
| `test_a_new_lever_starts_from_the_speed_last_asked_for` | 1 | monkeypatch |
| `test_clearing_the_throttle_drops_the_latch_as_well_as_the_lever` | 1 | monkeypatch |
| `test_a_commit_the_engine_is_already_obeying_still_holds_the_handle` | 1 | monkeypatch |
| `test_a_cab_1_commit_takes_no_latch` | 1 | monkeypatch |
| `test_a_touch_drag_takes_the_lever_back_from_the_stick` | 1 | monkeypatch |
| `test_only_an_active_local_ramp_sets_the_display_and_gesture_baseline` | 12 | monkeypatch, ramp_status, requested_speed |
| `test_ramp_ownership_comes_from_the_throttle_state_not_the_selected_engine` | 2 | monkeypatch, owns_ramp |
| `test_a_local_ramp_refresh_does_not_move_a_held_gesture` | 2 | held, monkeypatch |
| `test_a_ramp_accepted_while_the_lever_is_held_does_not_leave_a_pending_commit` | 1 | monkeypatch |
| `test_a_database_target_cannot_acknowledge_a_pending_direct_gesture` | 1 | monkeypatch |
| `test_a_new_gesture_does_not_revive_an_expired_direct_commit` | 1 | monkeypatch |
| `test_an_active_local_ramp_outlives_the_direct_commit_grace` | 1 | monkeypatch |
| `test_releasing_a_local_ramp_immediately_releases_commit_protection` | 8 | monkeypatch, refresh_before_release, release |
| `test_a_commit_at_actual_speed_still_redirects_an_active_ramp` | 1 | monkeypatch |
| `test_remote_claim_disables_slider_discards_intent_and_reenables_on_release` | 1 | monkeypatch |
| `test_claim_notifications_repaint_throttle_without_speed_changes` | 4 | address, monkeypatch, scope, state_type |
| `test_remote_claim_blocks_throttle_input_before_display_refresh` | 6 | monkeypatch, route |
| `test_rejected_ramp_reconciles_pending_gesture_without_ui_exception` | 1 | monkeypatch |
| `test_only_explicit_remote_ownership_blocks_the_local_owner` | 3 | monkeypatch, remote |
| `test_remote_claim_blocks_native_slider_events` | 7 | details, event_type, monkeypatch |
| `test_remote_claim_cancels_cab1_repeat_and_requires_fresh_mouse_press` | 1 | monkeypatch |
| `test_remote_claim_does_not_rearm_a_held_arrow_key_on_release` | 1 | monkeypatch |
| `test_x11_auto_repeat_cannot_rearm_a_key_held_during_a_remote_claim` | 1 | monkeypatch |
| `test_remote_claim_ends_native_mouse_repeat_and_drag` | 2 | button, monkeypatch |
| `test_remote_claim_paints_a_scale_that_ignores_set_while_disabled` | 1 | monkeypatch |
| `test_pending_cab1_callback_does_not_resume_when_claim_is_released` | 1 | monkeypatch |

## tests/gui/controller/test_controls_panel.py

119 cases; 78 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_bundled_profile_fits_on_one_page` | 1 |  |
| `test_the_last_column_holds_only_the_per_panel_sections` | 10 | budget |
| `test_the_bundled_columns_add_up_with_a_row_to_spare` | 1 |  |
| `test_a_section_that_starts_a_column_gets_one_of_its_own` | 1 | monkeypatch |
| `test_only_the_first_chunk_of_a_split_section_starts_a_column` | 1 |  |
| `test_no_column_exceeds_its_row_budget` | 1 |  |
| `test_pagination_loses_no_entries` | 1 |  |
| `test_a_section_taller_than_a_column_is_split_and_marked` | 1 |  |
| `test_split_preserves_the_fixed_flag` | 1 |  |
| `test_no_profile_paginates_to_nothing` | 1 |  |
| `test_turn_page_wraps_in_both_directions` | 1 |  |
| `test_turn_page_is_a_no_op_on_a_single_page` | 1 |  |
| `test_engine_gui_delegates_the_controls_screen_to_its_host` | 1 |  |
| `test_standalone_engine_gui_has_no_controls_screen` | 1 |  |
| `test_pane_reports_and_pages_the_hosts_screen` | 1 |  |
| `test_pane_without_a_host_reports_no_controls_screen` | 1 |  |
| `test_a_long_entry_is_budgeted_two_rows` | 1 |  |
| `test_section_rows_counts_the_header_and_wrapped_entries` | 1 |  |
| `test_a_section_note_costs_the_column_a_row` | 1 |  |
| `test_a_split_section_keeps_its_note_on_the_last_chunk` | 1 |  |
| `test_columns_respect_the_row_budget_once_wrapping_is_counted` | 1 |  |
| `test_bundled_profile_still_fits_one_page_with_wrapping` | 1 |  |
| `test_the_action_text_is_configured_to_wrap` | 1 | monkeypatch |
| `test_the_action_text_is_drawn_a_weight_lighter_than_its_keycap` | 1 | monkeypatch |
| `test_the_rows_are_drawn_at_the_size_that_was_fitted` | 1 | monkeypatch |
| `test_the_wrap_predictor_agrees_with_the_pixel_budget` | 1 |  |
| `test_a_measured_ruler_catches_the_wrap_the_character_count_missed` | 1 |  |
| `test_a_ruler_measures_each_string_once` | 1 |  |
| `test_the_packer_never_measures_a_string_twice` | 1 |  |
| `test_an_unmeasurable_widget_leaves_the_estimate_in_place` | 1 |  |
| `test_a_measured_ruler_reports_the_font_tk_will_draw_in` | 1 |  |
| `test_the_row_budget_is_divided_out_of_the_room_available` | 1 |  |
| `test_the_budget_never_promises_more_rows_than_the_display_holds` | 1 |  |
| `test_build_derives_the_budget_from_the_room_it_is_given` | 1 | monkeypatch |
| `test_the_entry_size_is_not_traded_for_a_wrapped_row` | 1 | monkeypatch |
| `test_a_lowered_floor_brings_the_shrink_back` | 1 | monkeypatch |
| `test_the_entry_size_is_never_given_back_past_the_floor` | 1 | monkeypatch |
| `test_the_size_ceiling_does_not_cost_the_screen_a_page` | 1 | monkeypatch |
| `test_an_unmeasurable_screen_draws_at_the_size_as_written` | 1 |  |
| `test_no_bundled_entry_is_predicted_to_wrap` | 1 |  |
| `test_the_middle_column_hands_its_width_to_the_two_beside_it` | 1 |  |
| `test_the_even_split_never_adds_up_past_the_room_it_was_given` | 5 | width |
| `test_no_measured_column_is_handed_less_than_its_rows_need` | 20 | needs, width |
| `test_the_columns_are_cut_to_what_their_rows_need` | 1 |  |
| `test_a_page_too_narrow_for_its_columns_overruns_rather_than_trimming_them` | 1 |  |
| `test_no_bundled_row_wraps_however_wide_the_display_draws_it` | 4 | monkeypatch, px_per_char |
| `test_no_throttle_note_wraps_whichever_commit_policy_is_selected` | 3 | monkeypatch, policy |
| `test_the_columns_are_grown_until_the_sections_that_moved_fit` | 1 | monkeypatch |
| `test_the_columns_stop_growing_after_a_bounded_number_of_passes` | 1 | monkeypatch |
| `test_the_slack_is_handed_to_the_columns_rather_than_held_back` | 1 |  |
| `test_nothing_to_measure_with_leaves_the_even_split` | 1 |  |
| `test_no_width_known_leaves_every_column_sizing_to_its_content` | 1 |  |
| `test_a_keycap_is_measured_in_the_weight_it_is_drawn_in` | 1 |  |
| `test_a_rows_note_is_priced_at_the_size_it_is_drawn_at` | 1 |  |
| `test_a_section_is_only_charged_for_the_notes_it_has` | 1 |  |
| `test_a_note_is_never_drawn_larger_than_the_row_it_qualifies` | 1 |  |
| `test_a_section_wraps_within_what_its_keycaps_leave_of_the_column` | 1 |  |
| `test_a_section_is_priced_by_the_column_it_is_packed_into` | 1 |  |
| `test_only_the_outer_columns_are_pinned_and_only_to_each_other` | 1 | monkeypatch |
| `test_the_outer_columns_are_not_matched_past_the_display` | 1 | monkeypatch |
| `test_the_columns_are_filled_after_everything_else_is_on_the_page` | 1 | monkeypatch |
| `test_a_render_tk_cannot_measure_leaves_the_columns_alone` | 1 | monkeypatch |
| `test_a_section_note_is_drawn_under_its_rows` | 1 | monkeypatch |
| `test_every_section_note_on_the_page_is_drawn` | 1 | monkeypatch |
| `test_the_action_text_wraps_within_its_own_column` | 1 | monkeypatch |
| `test_a_rows_note_is_drawn_beside_it_a_size_down` | 1 | monkeypatch |
| `test_a_row_with_no_note_spans_the_column_the_notes_use` | 1 | monkeypatch |
| `test_a_row_is_built_in_a_single_call` | 1 | monkeypatch |
| `test_the_rows_carry_no_grid_padding` | 1 | monkeypatch |
| `test_the_rows_are_told_the_colour_their_section_is_drawn_in` | 1 | monkeypatch |
| `test_the_rows_are_drawn_in_the_font_the_ruler_measured` | 1 | monkeypatch |
| `test_a_heading_splits_into_what_is_scanned_and_what_qualifies_it` | 5 | expected, title |
| `test_a_heading_qualifier_is_drawn_a_size_down` | 1 | monkeypatch |
| `test_a_heading_with_nothing_to_qualify_is_left_as_one_string` | 1 | monkeypatch |
| `test_a_heading_tk_cannot_split_is_drawn_in_one_size` | 1 | monkeypatch |
| `test_a_real_labelframe_accepts_the_split_heading` | 1 |  |
| `test_the_sections_are_outlined_in_a_single_line` | 1 | monkeypatch |
| `test_every_bundled_section_is_drawable_within_its_column` | 1 |  |

## tests/gui/controller/test_engine_gui_compatibility.py

80 cases; 60 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_remote_claim_blocks_speed_requests_and_allows_fresh_request_after_release` | 3 | monkeypatch, speed |
| `test_remote_claim_does_not_block_emergency_stop_speed_mapping` | 1 | monkeypatch |
| `test_ramp_rejection_race_does_not_raise_from_speed_callback` | 2 | monkeypatch, stage |
| `test_remote_claim_blocks_commands_that_bypass_the_speed_callback` | 5 | command, monkeypatch |
| `test_mapped_speed_rejection_race_does_not_raise_from_command_callback` | 2 | monkeypatch, stage |
| `test_remote_claim_does_not_block_safety_command_dispatch` | 5 | command, monkeypatch |
| `test_default_constructor_preserves_standalone_portrait_options` | 1 | monkeypatch |
| `test_standalone_emergency_row_keeps_local_halt_and_reset` | 1 | monkeypatch |
| `test_halt_command_is_dispatched_immediately_on_calling_thread` | 1 | monkeypatch |
| `test_engine_command_splits_targets_and_preserves_dispatch_order` | 1 |  |
| `test_horn_command_sounds_quilling_horn_with_intensity_for_legacy_engine` | 1 |  |
| `test_horn_command_falls_back_to_blow_horn_for_non_legacy_engine` | 1 |  |
| `test_an_aliased_button_sends_exactly_what_the_button_it_copies_sends` | 5 | alias, monkeypatch, real |
| `test_a_command_that_is_not_an_alias_is_passed_through_untouched` | 1 |  |
| `test_destroy_gui_releases_standalone_subscriptions_and_widget_cache` | 1 | monkeypatch |
| `test_embedded_constructor_uses_parent_root_and_owner_queue` | 1 | monkeypatch |
| `test_invalid_embedded_parent_combinations_are_rejected` | 3 | parent, parent_gui, stand_alone |
| `test_embedded_emergency_row_can_hide_halt_without_removing_reset` | 1 | monkeypatch |
| `test_compact_emergency_row_uses_short_actions_and_minimal_padding` | 1 | monkeypatch |
| `test_scope_row_wears_its_color_as_a_border_without_taking_more_room` | 3 | compact, expected_height, monkeypatch, scale |
| `test_compact_info_text_expands_vertically_within_road_fields` | 1 | monkeypatch |
| `test_compact_keypad_uses_ascii_enter_label_without_changing_command_value` | 1 |  |
| `test_compact_image_baseline_is_positive_and_bounded_by_pane` | 1 |  |
| `test_portrait_image_baseline_matches_the_measurements_taken_on_the_pi` | 1 |  |
| `test_the_baseline_reserves_nothing_for_the_controller_info_row_by_default` | 1 |  |
| `test_a_pane_keeps_its_id_row_and_its_title_rows_however_a_popup_is_drawn` | 1 |  |
| `test_a_reserved_info_row_is_taken_out_of_the_image_and_nothing_else` | 1 |  |
| `test_compact_image_box_is_three_times_wider_and_height_limited` | 1 |  |
| `test_compact_image_scaling_preserves_source_aspect_ratio` | 1 |  |
| `test_info_box_height_is_bounded_only_in_compact_mode` | 1 |  |
| `test_destroy_embedded_finalizes_child_without_destroying_shared_app` | 1 |  |
| `test_embedded_build_uses_pane_root_and_relative_popup_position` | 1 | monkeypatch |
| `test_portrait_build_reserves_the_bottom_edge_before_anything_is_packed` | 1 | monkeypatch |
| `test_linked_car_contract_is_read_only_and_selects_through_public_transition` | 1 |  |
| `test_active_selection_only_reflects_current_scope` | 1 |  |
| `test_missing_linked_car_states_do_not_break_train_selection` | 1 |  |
| `test_on_admin_command_starts_the_panel_button_hold_when_visible` | 1 |  |
| `test_on_admin_command_release_cancels_the_hold` | 1 |  |
| `test_on_admin_command_refuses_to_start_when_the_panel_is_hidden` | 1 |  |
| `test_on_admin_command_still_cancels_when_the_panel_is_hidden` | 1 |  |
| `test_on_admin_command_rejects_an_unknown_command` | 1 |  |
| `test_admin_visible_is_false_without_a_panel` | 1 |  |
| `test_a_press_on_the_picture_is_left_to_its_own_detector_either_binding` | 1 |  |
| `test_a_press_beside_the_picture_is_claimed_by_the_area_detector` | 1 |  |
| `test_a_press_below_the_image_band_is_rejected` | 1 |  |
| `test_nothing_is_claimed_while_the_image_box_is_unmapped` | 1 |  |
| `test_the_pane_exposes_an_open_chooser_for_the_dpad` | 1 |  |
| `test_a_pane_with_no_chooser_reports_nothing_to_drive` | 1 |  |
| `test_a_pane_with_no_state_info_panel_yet_is_safe_to_ask` | 1 |  |
| `test_the_pane_exposes_an_open_lcs_config_panel_for_the_pad` | 1 |  |
| `test_the_pane_reports_what_the_lcs_config_panel_answered` | 1 |  |
| `test_a_pane_whose_lcs_config_panel_is_closed_reports_nothing_to_drive` | 1 |  |
| `test_a_pane_that_has_never_opened_the_lcs_config_panel_is_safe_to_ask` | 1 |  |
| `test_the_pane_hands_the_lcs_config_panel_the_pixels_it_was_asked_for` | 1 |  |
| `test_the_pane_reports_whether_the_lcs_config_panel_page_moved` | 1 |  |
| `test_a_pane_whose_lcs_config_panel_is_closed_has_no_page_to_scroll` | 1 |  |
| `test_a_pane_that_has_never_opened_the_lcs_config_panel_is_safe_to_scroll` | 1 |  |
| `test_a_rail_road_speed_is_driven_by_the_threaded_ramper` | 1 | monkeypatch |
| `test_a_held_rail_road_speed_button_ramps_with_its_dialog` | 1 | monkeypatch |
| `test_a_cab1_engine_is_still_driven_relatively` | 1 | monkeypatch |

## tests/gui/controller/test_engine_gui_conf_import.py

3 cases; 3 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_importing_engine_gui_conf_does_not_call_find_file` | 1 |  |
| `test_engine_type_to_image_mapping_api_is_preserved` | 1 |  |
| `test_image_for_engine_type_matches_mapping` | 1 |  |

## tests/gui/controller/test_flatpak_admin_actions.py

14 cases; 9 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_flatpak_restart_requests_clean_local_shutdown` | 1 |  |
| `test_flatpak_local_power_commands_are_noops` | 2 | command |
| `test_conda_restart_uses_existing_dispatch` | 1 | monkeypatch |
| `test_flatpak_update_requests_host_install_then_local_restart` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_flatpak_update_without_available_release_does_nothing` | 1 |  |
| `test_flatpak_all_scope_forwards_power_command` | 2 | command |
| `test_flatpak_scope_change_toggles_power_buttons` | 1 |  |
| `test_initially_disabled_admin_button_remains_registered_for_chords` | 1 | monkeypatch |
| `test_server_gui_quit_broadcasts_and_closes_without_tmcc_or_restart` | 4 | scope, tag |

## tests/gui/controller/test_flatpak_update_indicator.py

9 cases; 9 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_available_release_changes_button_label` | 1 | monkeypatch |
| `test_up_to_date_keeps_original_label` | 1 | monkeypatch |
| `test_network_error_does_not_claim_an_update` | 1 | monkeypatch |
| `test_non_flatpak_never_starts_update_check` | 1 | monkeypatch |
| `test_single_flight_and_cached_result` | 1 | monkeypatch |
| `test_pending_update_schedules_tk_poll` | 1 |  |
| `test_pending_update_polls_before_overlay_is_visible` | 1 |  |
| `test_reopening_admin_starts_fresh_background_check` | 1 | monkeypatch |
| `test_stale_update_result_cannot_override_new_opening` | 1 | monkeypatch |

## tests/gui/controller/test_popup_manager_compatibility.py

69 cases; 63 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_create_popup_is_app_rooted_hidden_and_does_not_repack_host` | 1 | monkeypatch |
| `test_get_or_create_caches_overlay_by_key` | 1 | monkeypatch |
| `test_show_and_close_restore_host_content_image_and_accessory` | 1 |  |
| `test_editor_can_refuse_requested_close_and_replacement` | 1 |  |
| `test_failed_show_restores_content_and_image_and_button_state` | 1 |  |
| `test_embedded_popup_is_parented_and_layout_suspended_within_host_root` | 1 | monkeypatch |
| `test_compact_close_button_uses_reduced_height_without_changing_portrait` | 1 | monkeypatch |
| `test_a_footer_button_records_the_packing_it_was_given` | 1 |  |
| `test_footer_buttons_are_styled_identically_in_each_mode` | 1 |  |
| `test_restoring_replays_only_the_buttons_that_were_styled` | 1 |  |
| `test_repadding_a_footer_button_is_what_gets_replayed_afterwards` | 1 |  |
| `test_repadding_a_button_that_was_never_styled_still_records_the_ask` | 1 |  |
| `test_a_hidden_button_is_not_re_packed_and_so_stays_off_the_row` | 1 |  |
| `test_adding_close_repairs_the_packing_of_the_button_beside_it` | 1 | monkeypatch |
| `test_compact_footer_buttons_stay_tighter_than_portrait` | 1 |  |
| `test_the_footer_spacer_tracks_the_mode` | 1 |  |
| `test_the_leftover_space_all_goes_below_the_footer_row` | 1 | monkeypatch |
| `test_the_row_sits_a_fixed_distance_below_the_content` | 2 | compact, expected, monkeypatch |
| `test_the_compact_lead_is_what_a_centred_row_used_to_look_like` | 1 |  |
| `test_the_lead_is_created_after_the_row_so_a_tight_band_loses_whitespace_not_buttons` | 1 | monkeypatch |
| `test_create_popup_positions_the_footer_row_of_every_panel_it_builds` | 1 | monkeypatch |
| `test_a_panel_that_declines_close_is_given_none_but_keeps_its_whitespace` | 1 | monkeypatch |
| `test_a_panel_may_ask_for_a_tighter_footer_band` | 1 | monkeypatch |
| `test_every_panel_but_the_one_that_says_otherwise_gets_close` | 1 |  |
| `test_every_panel_but_the_one_that_says_otherwise_gets_the_shared_footer_band` | 1 |  |
| `test_every_panel_but_the_one_that_says_otherwise_closes_whenever_the_pane_says_so` | 1 |  |
| `test_a_panel_that_closes_only_on_request_says_so_as_it_is_built` | 1 | monkeypatch |
| `test_the_close_button_asks_rather_than_closing_in_passing` | 1 | monkeypatch |
| `test_a_panel_the_operator_is_working_in_is_not_closed_by_the_pane_in_passing` | 1 |  |
| `test_the_panel_the_pane_could_not_close_goes_when_it_is_asked_to` | 1 |  |
| `test_another_screen_still_takes_the_place_of_a_panel_that_holds_the_screen` | 1 |  |
| `test_a_popup_that_went_says_so_and_so_does_a_screen_with_nothing_in_the_way` | 1 |  |
| `test_create_popup_leaves_the_overlay_unsized` | 1 | monkeypatch |
| `test_showing_a_panel_extends_it_to_the_scope_row_and_closing_gives_it_back` | 2 | compact |
| `test_a_popup_that_failed_to_appear_is_left_collapsed` | 1 |  |
| `test_closing_restores_whatever_height_the_overlay_was_built_with` | 1 |  |
| `test_an_overlay_marked_no_expand_is_left_alone` | 1 |  |
| `test_accessory_popups_are_marked_no_expand_when_built` | 1 | monkeypatch |
| `test_a_roomy_band_keeps_the_fixed_lead_and_changes_nothing` | 2 | compact, monkeypatch |
| `test_a_band_tighter_than_the_lead_centres_the_row` | 4 | below, compact, expected, monkeypatch |
| `test_the_correction_settles_instead_of_creeping` | 1 | monkeypatch |
| `test_the_band_a_panel_asked_for_is_the_one_the_correction_measures_against` | 1 |  |
| `test_a_tight_band_is_still_evened_up_around_the_band_a_panel_asked_for` | 1 |  |
| `test_an_unmapped_overlay_is_not_measured` | 1 | monkeypatch |
| `test_a_popup_with_no_recorded_spacers_is_left_alone` | 1 |  |
| `test_create_popup_records_the_spacer_pair_for_every_panel` | 1 | monkeypatch |
| `test_show_runs_the_correction_pass` | 1 | monkeypatch |
| `test_a_popup_that_failed_to_appear_is_not_balanced` | 1 |  |
| `test_a_popup_title_is_centered_in_its_row` | 1 | monkeypatch |
| `test_centering_the_title_does_not_resize_its_row` | 1 | monkeypatch |
| `test_a_multi_line_title_still_gets_a_taller_row` | 1 | monkeypatch |
| `test_a_portrait_title_is_nudged_down_off_the_rows_top_edge` | 1 | monkeypatch |
| `test_a_compact_title_is_not_nudged` | 1 | monkeypatch |
| `test_a_title_row_is_not_resized_for_a_host_that_keeps_the_measured_height` | 1 | monkeypatch |
| `test_a_host_may_grow_the_title_row_to_the_title_it_holds` | 1 | monkeypatch |
| `test_a_row_already_deep_enough_is_left_alone_by_the_same_host` | 1 | monkeypatch |
| `test_a_compact_title_is_measured_without_the_nudge_it_never_gets` | 1 | monkeypatch |
| `test_a_panel_that_will_not_fit_is_given_the_id_rows_height_and_handed_it_back` | 1 |  |
| `test_a_panel_that_fits_leaves_the_id_row_where_it_is` | 1 |  |
| `test_the_id_row_is_never_taken_where_the_host_has_not_offered_it` | 1 |  |
| `test_a_popup_shown_before_the_pane_is_laid_out_leaves_the_row_alone` | 1 |  |
| `test_a_host_with_no_id_row_to_offer_is_no_obstacle` | 1 |  |
| `test_a_row_that_cannot_be_measured_is_not_one_the_close_puts_back` | 1 |  |

## tests/gui/controller/test_rr_speed_panel.py

6 cases; 6 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_every_cell_is_given_a_border_to_carry_its_color` | 1 | monkeypatch |
| `test_the_speed_in_force_is_the_only_one_wearing_the_selection_color` | 1 | monkeypatch |
| `test_no_speed_is_marked_while_nothing_is_selected` | 1 | monkeypatch |
| `test_the_emergency_cell_keeps_white_text_where_its_red_face_is_painted` | 1 | monkeypatch |
| `test_the_emergency_cell_takes_the_red_for_its_label_where_the_face_is_not_painted` | 1 | monkeypatch |
| `test_the_emergency_cell_is_not_one_of_the_speeds_to_choose_between` | 1 | monkeypatch |

## tests/gui/controller/test_steam_deck_input.py

493 cases; 366 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_profile_rejects_unknown_actions_and_unsafe_axis_targets` | 1 |  |
| `test_profile_defaults_and_validates_the_throttle_lead` | 1 |  |
| `test_bundled_profile_records_the_throttle_lead_defaults` | 1 |  |
| `test_profile_defaults_and_validates_the_throttle_commit_policy` | 1 |  |
| `test_bundled_profile_records_the_throttle_commit_defaults` | 1 |  |
| `test_invalid_external_profile_falls_back_to_bundled_default` | 1 | tmp_path, tmp_path_factory |
| `test_bundled_profile_maps_right_stick_to_steam_input_axes` | 1 |  |
| `test_bundled_profile_binds_view_button_to_focus_toggle` | 1 |  |
| `test_focus_toggle_requires_global_target` | 1 |  |
| `test_focus_toggle_routes_to_registered_global_action` | 1 |  |
| `test_bundled_profile_binds_menu_button_to_scope_catalog` | 1 |  |
| `test_bundled_profile_binds_shoulder_buttons_to_couplers` | 1 |  |
| `test_rear_coupler_button_opens_rear_coupler` | 1 |  |
| `test_front_coupler_button_opens_front_coupler` | 1 |  |
| `test_dpad_scrolls_catalog_in_focused_panel_when_visible` | 1 |  |
| `test_dpad_up_down_boost_brake_when_catalog_hidden` | 1 |  |
| `test_dpad_up_repeats_catalog_scroll_after_initial_delay` | 1 |  |
| `test_dpad_down_repeats_catalog_scroll_after_initial_delay` | 1 |  |
| `test_dpad_release_stops_catalog_scroll_repeat` | 1 |  |
| `test_dpad_scroll_repeat_stops_when_catalog_closes` | 1 |  |
| `test_dpad_left_right_smoke_does_not_repeat_when_catalog_hidden` | 1 |  |
| `test_dpad_right_selects_catalog_entry_when_visible` | 1 |  |
| `test_dpad_left_closes_catalog_when_visible` | 1 |  |
| `test_dpad_left_right_adjust_smoke_when_catalog_hidden` | 1 |  |
| `test_dpad_up_boosts_engine_speed_when_catalog_hidden` | 1 |  |
| `test_dpad_down_brakes_engine_speed_when_catalog_hidden` | 1 |  |
| `test_dpad_left_right_do_not_boost_or_brake_when_catalog_visible` | 1 |  |
| `test_dpad_up_repeats_boost_every_tick_while_held` | 1 |  |
| `test_dpad_down_repeats_brake_every_tick_while_held` | 1 |  |
| `test_dpad_release_stops_boost_repeat` | 1 |  |
| `test_dpad_up_down_do_not_boost_or_brake_when_catalog_visible` | 1 |  |
| `test_r1_plus_dpad_up_jumps_to_catalog_top_without_selecting` | 1 |  |
| `test_r1_plus_dpad_down_jumps_to_catalog_end_without_selecting` | 1 |  |
| `test_r1_opens_no_coupler_while_the_catalog_is_open` | 1 |  |
| `test_l1_still_opens_its_coupler_while_the_catalog_is_open` | 1 |  |
| `test_shoulder_buttons_open_couplers_when_catalog_closed` | 1 |  |
| `test_catalog_jump_cancels_pending_auto_repeat` | 1 |  |
| `test_dpad_without_the_modifier_only_ever_scrolls_one_entry` | 1 |  |
| `test_jump_modifier_still_boosts_when_catalog_closed` | 1 |  |
| `test_bundled_profile_binds_the_catalog_jump_modifier` | 1 |  |
| `test_bundled_profile_binds_the_back_paddles` | 1 |  |
| `test_button_repeat_interval_overrides_the_profile_cadence` | 1 |  |
| `test_button_without_an_override_uses_the_profile_cadence` | 1 |  |
| `test_profile_rejects_repeat_interval_without_repeat` | 1 |  |
| `test_profile_rejects_an_out_of_range_repeat_interval` | 1 |  |
| `test_paddle_actions_send_their_engine_command` | 4 | action_name, command |
| `test_paddle_commands_resolve_for_both_engine_generations` | 1 |  |
| `test_provider_flags_jump_modifier_while_r1_held` | 1 |  |
| `test_provider_does_not_flag_jump_modifier_once_r1_released` | 1 |  |
| `test_provider_does_not_flag_jump_modifier_for_l1` | 1 |  |
| `test_admin_chord_press_and_release_drive_the_panel_button` | 4 | action_name, command |
| `test_admin_chord_is_dropped_by_a_gui_that_has_no_admin_panel` | 1 |  |
| `test_l1_opens_no_coupler_while_the_admin_panel_is_open` | 1 |  |
| `test_l1_still_opens_its_coupler_when_the_admin_panel_is_closed` | 1 |  |
| `test_provider_emits_admin_chord_and_suppresses_the_second_button` | 4 | action_name, second_button |
| `test_admin_chord_reports_press_and_release_and_rearms` | 1 |  |
| `test_bundled_profile_defines_the_admin_chords` | 1 |  |
| `test_provider_translates_dpad_hat_to_one_shot_scroll_actions` | 1 |  |
| `test_provider_translates_dpad_hat_to_one_shot_left_right_actions` | 1 |  |
| `test_scope_catalog_invokes_scope_hold_on_focused_panel` | 1 |  |
| `test_select_button_confirms_catalog_entry_when_catalog_visible` | 1 |  |
| `test_select_button_performs_assigned_action_when_catalog_hidden` | 1 |  |
| `test_non_select_button_ignores_catalog_visibility` | 1 |  |
| `test_close_popup_button_closes_popup_when_popup_visible` | 1 |  |
| `test_close_popup_button_performs_assigned_action_when_no_popup` | 1 |  |
| `test_non_close_button_ignores_popup_visibility` | 1 |  |
| `test_provider_reports_button_index_for_button_actions` | 1 |  |
| `test_provider_applies_dead_zone_hysteresis_and_axis_inversion` | 1 |  |
| `test_provider_start_isolates_sdl_video_from_tk_touchscreen` | 1 | monkeypatch |
| `test_provider_start_wraps_only_sdl_runtime_errors` | 1 |  |
| `test_remote_claim_blocks_stick_until_neutral_and_keeps_other_pane_usable` | 6 | is_cab1, policy |
| `test_remote_claim_drops_held_or_pending_settle_before_tick` | 2 | settling |
| `test_remote_claim_keeps_direction_reset_halt_and_shutdown_operational` | 1 |  |
| `test_remote_claim_discards_held_speed_mapping_without_resuming_it` | 4 | action, held_before_claim |
| `test_claim_and_release_between_ticks_still_discards_the_old_stick_gesture` | 2 | tick_before_claim |
| `test_claim_and_release_between_ticks_discards_a_boost_repeat` | 1 |  |
| `test_held_throttle_moves_the_lever_and_commands_only_its_lead` | 1 |  |
| `test_the_first_throttle_command_leads_the_lever_rather_than_matching_it` | 1 |  |
| `test_a_long_throttle_hold_re_leads_no_faster_than_the_minimum_interval` | 1 |  |
| `test_throttle_commits_once_when_the_stick_returns_to_center` | 1 |  |
| `test_a_throttle_pulled_back_lowers_the_lever_and_stops_at_zero` | 1 |  |
| `test_a_throttle_lever_is_dropped_without_a_further_command_when_the_pad_disconnects` | 1 |  |
| `test_the_release_policy_says_nothing_until_the_stick_is_let_go` | 1 |  |
| `test_the_dwell_policy_commits_while_the_stick_is_held_steady` | 1 |  |
| `test_the_dwell_policy_restarts_its_clock_when_the_stick_moves` | 1 |  |
| `test_the_dwell_policy_reads_a_jittering_thumb_as_a_hold` | 1 |  |
| `test_a_move_out_of_the_steady_band_restarts_the_dwell_clock` | 1 |  |
| `test_the_dwell_policy_re_anchors_its_band_where_the_thumb_now_is` | 1 |  |
| `test_cab1_rate_throttle_emits_bounded_relative_steps` | 1 |  |
| `test_direction_uses_hysteresis` | 2 | target |
| `test_moving_current_direction_is_noop` | 2 | is_forward, is_reverse, value |
| `test_moving_opposite_direction_executes_command` | 2 | command, is_forward, is_reverse, value |
| `test_buttons_route_to_focused_fixed_and_global_targets` | 1 |  |
| `test_disconnect_clears_active_throttle_without_issuing_stop` | 1 |  |
| `test_provider_reports_unavailable_configured_controls` | 1 |  |
| `test_emergency_chord_fires_once_until_released` | 1 |  |
| `test_bundled_profile_binds_right_stick_click_to_focus_right` | 1 |  |
| `test_startup_requires_a_panel_target` | 1 |  |
| `test_startup_immediate_action_starts_engine_immediately` | 1 |  |
| `test_startup_delayed_action_requests_delayed_startup_with_fallback` | 1 |  |
| `test_provider_short_press_emits_startup_immediate` | 1 |  |
| `test_provider_long_press_emits_startup_delayed` | 1 |  |
| `test_provider_startup_button_held_briefly_emits_nothing` | 1 |  |
| `test_provider_startup_button_hold_emits_startup_delayed_while_still_held` | 1 |  |
| `test_provider_holding_a_startup_button_into_a_chord_still_suppresses_it` | 1 |  |
| `test_provider_suppresses_startup_when_halt_chord_fires` | 1 |  |
| `test_bundled_profile_binds_left_stick_click_to_focus_left` | 1 |  |
| `test_shutdown_requires_a_panel_target` | 1 |  |
| `test_shutdown_immediate_action_shuts_engine_down_immediately` | 1 |  |
| `test_shutdown_delayed_action_requests_delayed_shutdown_with_fallback` | 1 |  |
| `test_provider_short_press_emits_shutdown_immediate` | 1 |  |
| `test_provider_long_press_emits_shutdown_delayed` | 1 |  |
| `test_provider_shutdown_button_held_briefly_emits_nothing` | 1 |  |
| `test_provider_shutdown_button_hold_emits_shutdown_delayed_while_still_held` | 1 |  |
| `test_provider_suppresses_shutdown_when_halt_chord_fires` | 1 |  |
| `test_provider_handles_disconnect_and_reconnect` | 1 |  |
| `test_bundled_profile_binds_triggers_to_startup_shutdown` | 1 |  |
| `test_axis_shutdown_action_requires_trigger_flag` | 1 |  |
| `test_axis_startup_action_requires_panel_target` | 1 |  |
| `test_provider_trigger_short_press_emits_shutdown_immediate` | 1 |  |
| `test_provider_trigger_long_press_emits_shutdown_delayed` | 1 |  |
| `test_provider_trigger_short_press_emits_startup_immediate` | 1 |  |
| `test_provider_trigger_long_press_emits_startup_delayed` | 1 |  |
| `test_provider_trigger_squeezed_briefly_emits_nothing` | 1 |  |
| `test_provider_trigger_hold_emits_shutdown_delayed_while_still_squeezed` | 1 |  |
| `test_provider_button_hold_fires_at_the_profiles_threshold` | 1 |  |
| `test_provider_trigger_hold_fires_at_the_profiles_threshold` | 1 |  |
| `test_provider_release_before_the_profiles_threshold_stays_immediate` | 1 |  |
| `test_provider_logs_the_profiles_threshold_rather_than_the_default` | 1 | caplog |
| `test_provider_logs_the_hold_that_reported_a_delayed_startup` | 1 | caplog |
| `test_provider_logs_the_trigger_travel_with_its_thresholds` | 1 | caplog |
| `test_provider_logs_a_poll_that_stalled_during_a_hold` | 1 | caplog |
| `test_provider_diagnostics_are_inert_without_debug` | 1 | caplog, monkeypatch |
| `test_provider_trigger_long_press_ignores_resting_position` | 1 |  |
| `test_axis_focus_action_requires_trigger_flag` | 1 |  |
| `test_axis_focus_action_requires_global_target` | 1 |  |
| `test_provider_trigger_button_fires_focus_once_per_squeeze` | 1 |  |
| `test_provider_right_trigger_fires_focus_right` | 1 |  |
| `test_provider_trigger_button_ignores_resting_position` | 1 |  |
| `test_trigger_focus_routes_to_registered_global_action` | 1 |  |
| `test_stick_axes_are_not_flagged_as_triggers` | 1 |  |
| `test_bundled_profile_uses_a_digital_trigger_dead_zone` | 1 |  |
| `test_bundled_trigger_dead_zone_reads_a_drifted_rest_as_rest` | 1 |  |
| `test_profile_warns_when_trigger_dead_zone_cannot_see_a_release` | 1 | caplog |
| `test_trigger_dead_zone_defaults_when_omitted` | 1 |  |
| `test_profile_rejects_out_of_range_trigger_dead_zone` | 1 |  |
| `test_profile_exposes_configured_long_press_seconds` | 1 |  |
| `test_long_press_seconds_defaults_when_omitted` | 1 |  |
| `test_bundled_profile_ships_default_long_press_seconds` | 1 |  |
| `test_profile_rejects_too_short_long_press_seconds` | 1 |  |
| `test_profile_rejects_too_long_long_press_seconds` | 1 |  |
| `test_provider_sounds_horn_just_past_trigger_rest` | 1 |  |
| `test_provider_normalizes_trigger_axis_from_resting_to_full` | 1 |  |
| `test_provider_emits_fractional_quilling_horn_for_partial_press` | 1 |  |
| `test_quilling_horn_press_and_release_update_router_state` | 1 |  |
| `test_tick_repeats_quilling_horn_with_scaled_intensity` | 1 |  |
| `test_tick_scales_quilling_horn_intensity_to_trigger_fraction` | 1 |  |
| `test_tick_clamps_light_quilling_horn_press_to_minimum_intensity` | 1 |  |
| `test_tick_stops_quilling_horn_after_release` | 1 |  |
| `test_bundled_profile_binds_a_button_to_sequence_control` | 1 |  |
| `test_bundled_profile_flags_x_and_y_buttons_as_repeat` | 1 |  |
| `test_button_repeat_flag_defaults_to_false` | 1 |  |
| `test_sequence_control_constants_match_automatic_sequence_spec` | 1 |  |
| `test_sequence_control_fires_immediately_and_schedules_full_burst` | 1 |  |
| `test_sequence_control_repeats_across_ticks_then_stops` | 1 |  |
| `test_sequence_control_confirms_catalog_entry_when_visible` | 1 |  |
| `test_repeat_button_repeats_command_each_tick_while_held` | 1 |  |
| `test_repeat_button_stops_on_release` | 1 |  |
| `test_repeat_close_popup_button_closes_popup_without_repeating` | 1 |  |
| `test_non_repeat_button_fires_once_and_is_not_stored` | 1 |  |
| `test_clear_resets_sequence_and_held_command_state` | 1 |  |
| `test_provider_ignores_duplicate_add_event_for_enumerated_device` | 1 | caplog |
| `test_bundled_profile_binds_touchpads_to_quilling_horn` | 1 |  |
| `test_bundled_profile_uses_small_touch_dead_zone` | 1 |  |
| `test_touch_dead_zone_defaults_when_omitted` | 1 |  |
| `test_profile_rejects_out_of_range_touch_dead_zone` | 1 |  |
| `test_profile_rejects_non_quilling_touchpad_action` | 1 |  |
| `test_profile_rejects_touchpad_without_fixed_panel_target` | 1 |  |
| `test_touchpad_binding_is_parsed_into_dataclass` | 1 |  |
| `test_normalize_touch_y_maps_top_to_off_and_bottom_to_full` | 1 |  |
| `test_provider_touch_down_then_motion_emits_quilling_horn_on_left_pad` | 1 |  |
| `test_provider_touch_on_right_pad_targets_right_panel` | 1 |  |
| `test_provider_touch_up_stops_the_horn_when_last_finger_lifts` | 1 |  |
| `test_provider_multi_finger_keeps_horn_until_last_finger_lifts` | 1 |  |
| `test_provider_ignores_touch_events_for_unmapped_pad` | 1 |  |
| `test_touch_drag_drives_router_quilling_horn_end_to_end` | 1 |  |
| `test_touch_release_stops_router_repeat` | 1 |  |
| `test_provider_without_touchpad_support_processes_joystick_only` | 1 |  |
| `test_provider_start_allows_touchpad_events_and_opens_controller` | 1 |  |
| `test_provider_start_without_controller_module_leaves_touchpad_disabled` | 1 |  |
| `test_remove_device_resets_touch_finger_state` | 1 |  |
| `test_decode_deck_pads_reads_touch_bits_and_coordinates` | 1 |  |
| `test_native_deck_stick_offsets_and_polarity` | 3 | raw |
| `test_native_deck_dpad_bits` | 5 | buttons, hat |
| `test_native_deck_controls_reject_incomplete_or_unrelated_reports` | 3 | report |
| `test_native_physical_stick_and_horn_work_simultaneously_despite_virtual_axis` | 2 | offset, side |
| `test_native_physical_dpad_press_and_release_ignore_virtual_hat` | 1 |  |
| `test_native_deck_filter_preserves_external_gamepads_and_sdl_fallback` | 2 | native |
| `test_native_deck_filter_does_not_take_triggers_or_buttons` | 1 |  |
| `test_native_deck_reader_timeout_clears_holds_without_accepting_emulated_input` | 1 |  |
| `test_native_deck_takeover_cancels_an_earlier_virtual_throttle_without_committing` | 1 |  |
| `test_native_deck_filter_recognizes_physical_and_virtual_device_identity` | 3 | guid, name |
| `test_native_trackpad_ignores_steam_input_joystick_and_dpad_emulation` | 4 | is_cab1, side |
| `test_native_trackpad_keeps_contextual_scrolling_without_emulated_stick_repeat` | 2 | panel_kind |
| `test_decode_deck_pads_reports_untouched_pads` | 1 |  |
| `test_decode_deck_pads_rejects_non_state_and_short_reports` | 1 |  |
| `test_deck_pad_y_fraction_maps_top_off_and_bottom_full` | 1 |  |
| `test_decode_deck_paddles_reads_each_paddle_bit` | 1 |  |
| `test_decode_deck_paddles_rejects_non_state_and_short_reports` | 1 |  |
| `test_hidraw_paddle_press_and_release_emit_one_action_each` | 1 |  |
| `test_hidraw_paddles_are_independent` | 1 |  |
| `test_paddle_reported_by_both_routes_fires_once` | 1 |  |
| `test_capability_warning_ignores_paddles_sdl_does_not_report` | 1 |  |
| `test_hidraw_pad_motion_emits_quilling_horn_for_bound_pads` | 1 |  |
| `test_hidraw_uses_only_latest_report_per_node` | 1 |  |
| `test_hidraw_release_emits_single_stop_when_finger_lifts` | 1 |  |
| `test_hidraw_ignores_unbound_pad` | 1 |  |
| `test_hidraw_reports_open_error_once` | 1 |  |
| `test_drain_hidraw_pads_is_noop_without_reader` | 1 |  |
| `test_start_hidraw_readers_skips_when_no_touchpads_bound` | 1 |  |
| `test_start_hidraw_readers_starts_thread_when_deck_node_present` | 1 | monkeypatch |
| `test_find_deck_hidraw_paths_returns_list` | 1 |  |
| `test_show_controls_opens_the_panel_on_press_only` | 1 |  |
| `test_show_controls_still_opens_while_the_screen_is_already_up` | 1 |  |
| `test_show_controls_is_dropped_when_no_handler_is_registered` | 1 |  |
| `test_engine_commands_are_dropped_while_the_controls_screen_is_up` | 1 |  |
| `test_dpad_up_down_pages_the_controls_screen` | 1 |  |
| `test_close_button_closes_the_controls_screen` | 1 |  |
| `test_close_button_is_tolerated_when_the_gui_cannot_close_it` | 1 |  |
| `test_engine_commands_flow_normally_once_the_screen_is_closed` | 1 |  |
| `test_bundled_profile_binds_show_controls_to_the_stick_clicks` | 1 |  |
| `test_the_misc_button_is_left_unbound` | 1 |  |
| `test_show_controls_must_target_global` | 1 |  |
| `test_dpad_drives_an_open_chooser_instead_of_the_engine` | 1 |  |
| `test_the_a_button_commits_an_open_chooser` | 1 |  |
| `test_a_release_is_swallowed_while_a_chooser_is_open` | 1 |  |
| `test_halt_still_works_while_a_chooser_is_open` | 1 |  |
| `test_the_dpad_reaches_the_engine_again_once_the_chooser_closes` | 1 |  |
| `test_the_dpad_works_an_open_lcs_config_panel_instead_of_the_engine` | 1 |  |
| `test_the_a_and_b_buttons_turn_the_lcs_config_panel_pages` | 1 |  |
| `test_the_close_button_still_closes_the_lcs_config_panel` | 1 |  |
| `test_no_release_is_claimed_while_the_lcs_config_panel_is_up` | 3 | action |
| `test_a_dpad_release_still_clears_a_boost_held_before_the_panel_opened` | 1 |  |
| `test_halt_still_works_while_the_lcs_config_panel_is_up` | 1 |  |
| `test_the_lcs_config_panel_leaves_no_boost_repeating_behind_it` | 1 |  |
| `test_the_dpad_reaches_the_engine_again_once_the_lcs_config_panel_closes` | 1 |  |
| `test_a_choice_list_opened_over_the_lcs_config_panel_still_wins` | 1 |  |
| `test_the_panes_own_stick_scrolls_the_lcs_config_panel_instead_of_driving` | 1 |  |
| `test_the_stick_pulled_back_scrolls_the_page_down_and_half_over_moves_half_as_far` | 1 |  |
| `test_the_stick_back_at_center_stops_scrolling_the_lcs_config_panel` | 1 |  |
| `test_each_stick_scrolls_its_own_panes_panel_rather_than_the_focused_ones` | 1 |  |
| `test_a_stick_already_held_when_the_lcs_config_panel_opens_lets_go_of_the_engine` | 1 |  |
| `test_a_horn_already_sounding_when_the_trackpad_takes_the_page_over_is_let_go_of` | 1 |  |
| `test_the_lcs_config_panel_closing_under_a_held_stick_drops_the_scroll` | 1 |  |
| `test_the_trackpad_scrolls_the_page_by_how_far_the_finger_has_traveled` | 1 |  |
| `test_a_finger_drawn_up_the_trackpad_scrolls_the_page_up` | 1 |  |
| `test_a_finger_lifted_from_the_trackpad_forgets_where_the_stroke_was` | 1 |  |
| `test_a_finger_still_down_when_the_panel_closes_is_forgotten_with_it` | 1 |  |
| `test_a_stick_held_through_a_panel_closing_and_opening_is_not_still_scrolling` | 1 |  |
| `test_a_pane_with_no_trackpad_bound_to_it_still_sounds_the_horn_over_the_panel` | 1 |  |
| `test_the_other_panes_trackpad_does_not_scroll_this_panes_page` | 1 |  |
| `test_the_stick_drives_the_engine_again_while_the_lcs_config_panel_is_down` | 1 |  |
| `test_a_disconnect_forgets_a_held_scroll_and_a_stroke_in_progress` | 1 |  |
| `test_list_sticks_scroll_both_panes_at_lcs_speed_independent_of_focus` | 1 |  |
| `test_list_scrolling_ignores_sideways_joystick_motion` | 3 | kind |
| `test_list_touchpad_tracks_travel_and_restarts_after_lift` | 1 |  |
| `test_list_scrolling_drops_held_input_when_its_view_is_gone` | 7 | stop |
| `test_list_opening_stops_preexisting_analog_commands_without_another_axis_event` | 1 |  |
| `test_list_leaves_unbound_horn_and_global_halt_available` | 1 |  |
| `test_list_takes_stick_from_accessory_and_releases_held_output` | 3 | kind |
| `test_list_closing_restarts_touchpad_stroke_and_returns_stick_to_engine` | 1 |  |
| `test_triggers_throw_the_switch_rather_than_starting_an_engine` | 6 | name, thru |
| `test_triggers_still_start_and_stop_an_engine_in_an_engine_panel` | 1 |  |
| `test_the_face_buttons_throw_the_switch_rather_than_working_an_engine` | 2 | button, name, thru |
| `test_the_face_buttons_still_work_the_engine_in_an_engine_panel` | 1 |  |
| `test_the_face_buttons_stand_aside_while_the_switch_catalog_is_open` | 1 |  |
| `test_a_face_button_held_as_the_panel_became_a_switch_stops_repeating` | 2 | button, command, name |
| `test_a_stick_pushed_sideways_throws_the_switch_thru_once_per_deflection` | 1 |  |
| `test_a_stick_pushed_vertically_throws_the_switch_out` | 1 |  |
| `test_a_stick_short_of_the_threshold_does_not_throw_the_switch` | 1 |  |
| `test_a_stick_on_a_switch_panel_does_not_drive_the_engine_it_last_held` | 1 |  |
| `test_each_stick_throws_the_switch_in_its_own_panel` | 1 |  |
| `test_a_stick_keeps_driving_the_engine_in_the_other_panel` | 1 |  |
| `test_triggers_fire_the_route_rather_than_starting_an_engine` | 6 | name |
| `test_triggers_still_start_and_stop_an_engine_in_a_panel_holding_no_route` | 1 |  |
| `test_the_a_button_fires_the_route_rather_than_working_an_engine` | 1 |  |
| `test_the_horn_button_is_swallowed_rather_than_firing_the_route` | 1 |  |
| `test_the_face_buttons_still_work_the_engine_in_a_panel_holding_no_route` | 1 |  |
| `test_the_face_buttons_stand_aside_while_the_route_catalog_is_open` | 1 |  |
| `test_a_face_button_held_as_the_panel_became_a_route_stops_repeating` | 2 | button, command, name |
| `test_a_stick_pushed_up_fires_the_route_once_per_deflection` | 1 |  |
| `test_a_stick_pushed_right_fires_the_route` | 1 |  |
| `test_a_stick_pulled_the_other_way_fires_nothing_and_drives_nothing` | 2 | name |
| `test_a_stick_short_of_the_threshold_does_not_fire_the_route` | 1 |  |
| `test_each_stick_fires_the_route_in_its_own_panel` | 1 |  |
| `test_fires_on_press_resolves_the_panel_a_target_names` | 1 |  |
| `test_provider_trigger_throws_a_switch_on_the_squeeze` | 1 |  |
| `test_provider_trigger_keeps_its_hold_behaviour_for_an_engine_panel` | 1 |  |
| `test_a_profile_with_no_dpad_section_keeps_what_the_dpad_always_did` | 1 |  |
| `test_a_dpad_section_rebinds_one_direction_and_leaves_the_others` | 1 |  |
| `test_a_dpad_direction_bound_to_null_is_switched_off_entirely` | 1 |  |
| `test_a_dpad_section_rejects_a_bad_direction_action_or_target` | 1 |  |
| `test_a_rebound_dpad_direction_sends_what_the_profile_says` | 1 |  |
| `test_a_repeat_flag_on_a_dpad_direction_is_what_makes_it_repeat` | 1 |  |
| `test_an_unrepeated_direction_release_does_not_cancel_a_repeat_running_on_the_other_axis` | 1 |  |
| `test_a_dpad_target_in_the_profile_is_the_target_the_provider_reports` | 1 |  |
| `test_a_profile_context_override_changes_what_a_control_does_on_a_panel` | 1 |  |
| `test_a_profile_may_unbind_a_context_entry` | 1 |  |
| `test_an_unbound_entry_is_still_swallowed_where_the_context_claims_what_it_has_not_bound` | 1 |  |
| `test_a_malformed_contexts_section_is_logged_and_the_defaults_stand` | 1 |  |
| `test_the_stick_drives_the_accessorys_speed_rather_than_an_engines` | 1 |  |
| `test_a_light_push_of_the_stick_is_still_a_step` | 1 |  |
| `test_the_horizontal_stick_toggles_the_accessorys_direction_either_way` | 2 | value |
| `test_a_held_stick_toggles_the_accessory_once_and_re_arms_only_near_center` | 1 |  |
| `test_the_power_district_stick_selects_off_or_on_by_sign` | 4 | expected, kind, value |
| `test_the_power_district_stick_latches_by_physical_axis_and_rearms_after_center` | 2 | kind |
| `test_the_shoulder_buttons_open_the_accessorys_couplers` | 2 | button, command, name |
| `test_the_dpad_boosts_and_brakes_the_accessory_and_repeats_while_held` | 2 | command, name |
| `test_a_dpad_repeat_started_on_an_accessory_panel_stops_when_the_pane_changes_scope` | 1 |  |
| `test_an_engine_only_control_is_claimed_and_dropped_on_the_accessory_panel` | 1 |  |
| `test_an_lcs_port_showing_the_generic_panel_takes_the_whole_set` | 1 |  |
| `test_the_generic_panel_leaves_set_address_alone` | 1 |  |
| `test_an_engine_panel_is_untouched_by_the_accessory_context` | 1 |  |
| `test_the_triggers_and_the_dpad_switch_a_power_district` | 16 | kind, name, on |
| `test_the_asc2_panel_inherits_the_power_district_pair_rather_than_restating_it` | 1 |  |
| `test_a_held_button_energises_the_asc2_output_and_the_release_drops_it` | 2 | button, name |
| `test_an_asc2_output_is_not_left_on_when_the_pane_changes_scope_under_the_thumb` | 1 |  |
| `test_the_vertical_stick_energises_the_asc2_output_while_it_is_held` | 2 | value |
| `test_the_asc2_stick_uses_the_same_hysteresis_band_as_the_latch` | 1 |  |
| `test_a_stick_resting_under_the_threshold_energises_nothing` | 1 |  |
| `test_the_asc2_output_stays_on_until_the_last_holder_lets_go` | 1 |  |
| `test_the_asc2_output_survives_the_stick_letting_go_first` | 1 |  |
| `test_a_held_stick_drops_the_asc2_output_even_after_the_pane_changes_scope` | 1 |  |
| `test_a_pad_that_disconnects_with_the_stick_pushed_over_does_not_leave_the_output_on` | 1 |  |
| `test_clear_switches_off_an_output_held_by_two_controls_once` | 1 |  |
| `test_the_vertical_stick_does_nothing_on_a_bare_power_district` | 1 |  |
| `test_a_diagonal_stick_holds_the_asc2_output_and_switches_the_district_at_once` | 1 |  |
| `test_the_generic_aux_keys_are_absent_from_a_power_district_or_asc2_panel` | 6 | kind, name |
| `test_neither_power_district_context_inherits_the_generic_one` | 2 | context |
| `test_the_dpad_steps_the_sequence_the_way_the_list_reads` | 2 | delta, name |
| `test_the_highlighted_sequence_is_written_when_it_is_selected` | 2 | button, name |
| `test_the_previous_sequence_is_put_back_when_the_choice_is_reverted` | 2 | button, name |
| `test_x_closes_a_popup_over_a_sensor_track_rather_than_reverting` | 1 |  |
| `test_crossing_the_whole_list_writes_nothing_until_it_is_selected` | 1 |  |
| `test_tick_never_writes_a_sequence_of_its_own_accord` | 1 |  |
| `test_a_held_select_writes_once_rather_than_repeatedly` | 1 |  |
| `test_a_press_clamped_at_either_end_moves_nothing_and_writes_nothing` | 2 | index, name |
| `test_a_held_dpad_steps_the_sequence_exactly_once` | 1 |  |
| `test_an_unset_sequence_is_stepped_onto_the_first_option_either_way` | 1 |  |
| `test_clear_writes_nothing_because_a_stepped_highlight_is_not_a_choice` | 1 |  |
| `test_two_panes_step_and_select_independently` | 1 |  |
| `test_the_sticks_on_a_sensor_track_panel_are_claimed_and_sent_nowhere` | 2 | name |
| `test_the_triggers_on_a_sensor_track_panel_are_claimed_and_sent_nowhere` | 2 | name |
| `test_menu_opens_the_catalog_from_every_accessory_panel` | 4 | kind |
| `test_x_closes_a_popup_over_every_accessory_panel` | 4 | kind |
| `test_x_with_no_popup_up_is_claimed_by_the_accessory_panel` | 3 | kind |
| `test_x_on_a_power_district_under_train_scope_puts_no_reset_on_the_wire` | 1 |  |
| `test_x_still_closes_a_popup_over_a_power_district_under_train_scope` | 1 |  |
| `test_menu_still_opens_the_catalog_with_a_popup_up` | 4 | kind |
| `test_an_open_catalog_gets_the_whole_dpad_back_from_an_accessory_panel` | 16 | catalog, kind, name, scrolls |
| `test_the_dpad_works_the_power_district_again_once_the_catalog_is_gone` | 2 | name |
| `test_an_asc2_output_held_by_the_dpad_is_dropped_when_the_catalog_opens_under_the_thumb` | 1 |  |
| `test_a_dpad_repeat_is_dropped_when_the_catalog_opens_under_the_thumb` | 1 |  |
| `test_the_dpad_released_after_the_catalog_took_it_scrolls_nothing_on_its_way_out` | 1 |  |
| `test_a_dpad_repeat_survives_a_catalog_open_over_a_pane_that_is_not_this_one` | 1 |  |
| `test_the_catalog_opened_over_a_panel_is_scrolled_by_the_next_press` | 1 |  |

## tests/gui/controller/test_steam_deck_packaging.py

5 cases; 5 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_runtime_dependencies_and_profile_are_packaged` | 1 |  |
| `test_launch_artifacts_preserve_gamescope_display_and_describe_kde_entry` | 1 |  |
| `test_bundled_profile_declares_the_dpad_rather_than_leaving_it_hard_coded` | 1 |  |
| `test_bundled_profile_sections_are_all_ones_the_loader_understands` | 1 |  |
| `test_bundled_profile_loads_with_the_dpad_and_context_tables_populated` | 1 |  |

## tests/gui/test_accessory_cache_root.py

3 cases; 3 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_accessory_config_uses_shared_cache_root` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_accessory_config_keeps_pi_lookup` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_explicit_config_path_is_unchanged` | 1 | monkeypatch, tmp_path, tmp_path_factory |

## tests/gui/test_amc2_ops_panel.py

14 cases; 14 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_build_and_update_from_state_sets_motor_page_values` | 1 | _patch_widgets, monkeypatch |
| `test_paging_shows_two_controls_per_page` | 1 | _patch_widgets, monkeypatch |
| `test_toggle_lamp_uses_actual_state_level` | 1 | _patch_widgets, monkeypatch |
| `test_external_light_zero_sets_button_and_trough_off` | 1 | _patch_widgets, monkeypatch |
| `test_the_nav_keys_stand_in_a_column_of_the_panel_beside_the_sliders` | 1 | _patch_widgets, monkeypatch |
| `test_the_nav_keys_are_exposed_for_the_keypad_to_wire` | 1 | _patch_widgets, monkeypatch |
| `test_the_nav_column_reserves_everything_its_keys_ask_for` | 1 | _patch_widgets, monkeypatch |
| `test_the_panel_measures_the_display_beside_it_and_never_its_own_contents` | 1 | _patch_widgets, monkeypatch |
| `test_the_sliders_are_laid_out_in_what_is_left_after_the_borders_and_the_keys` | 1 | _patch_widgets, monkeypatch |
| `test_each_page_option_is_centered_over_its_half_of_the_sliders` | 1 | _patch_widgets, monkeypatch |
| `test_each_nav_key_is_an_ops_key_square_stacked_from_the_top_of_the_panel` | 1 | _patch_widgets, monkeypatch |
| `test_an_output_label_is_drawn_at_the_largest_size_its_column_has_room_for` | 1 | _patch_widgets, monkeypatch |
| `test_the_lights_labels_are_sized_against_their_own_quarter_of_the_sliders` | 1 | _patch_widgets, monkeypatch |
| `test_the_page_options_are_left_alone_until_the_panel_has_been_measured` | 1 | _patch_widgets, monkeypatch |

## tests/gui/test_bundled_fonts.py

22 cases; 14 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_font_resource_is_independent_of_working_directory` | 2 | bundled_font, monkeypatch, package, tmp_path, tmp_path_factory |
| `test_zipped_package_font_stays_extracted_until_process_cleanup` | 1 | bundled_font, monkeypatch, tmp_path, tmp_path_factory |
| `test_simultaneous_requests_only_register_once` | 1 | bundled_font, monkeypatch |
| `test_registration_failure_is_logged_and_not_repeated` | 2 | bundled_font, caplog, error, monkeypatch |
| `test_missing_package_resource_is_a_nonfatal_failure` | 1 | bundled_font, caplog, monkeypatch, tmp_path, tmp_path_factory |
| `test_registration_does_not_swallow_cancellation` | 2 | bundled_font, error, monkeypatch |
| `test_resource_cleanup_failure_retains_extracted_path_for_retry` | 1 | bundled_font, caplog, monkeypatch, tmp_path, tmp_path_factory |
| `test_resource_cleanup_does_not_swallow_cancellation` | 2 | bundled_font, error, monkeypatch |
| `test_registration_uses_the_platform_backend` | 2 | backend, monkeypatch, platform |
| `test_unsupported_platform_does_not_attempt_native_registration` | 1 | monkeypatch |
| `test_macos_registration_has_process_scope_and_releases_native_resources` | 2 | monkeypatch, success |
| `test_macos_url_failure_does_not_register_an_invalid_pointer` | 1 | monkeypatch |
| `test_linux_uses_the_current_fontconfig_and_checks_success` | 3 | config, monkeypatch, success |
| `test_unavailable_native_library_is_reported` | 1 | monkeypatch |

## tests/gui/test_catalog_panel.py

15 cases; 10 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_controller_scroll_uses_visible_catalog_without_selecting` | 1 |  |
| `test_select_highlighted_delegates_to_catalog_list_box` | 1 |  |
| `test_select_highlighted_returns_false_without_catalog` | 1 |  |
| `test_move_highlight_delegates_to_catalog_list_box` | 1 |  |
| `test_move_highlight_returns_false_without_catalog` | 1 |  |
| `test_reset_configured_accessory_cache_clears_and_rebuilds_active_accessory_catalog` | 1 |  |
| `test_reset_configured_accessory_cache_does_not_build_missing_catalog` | 1 |  |
| `test_reset_configured_accessory_cache_rebuilds_from_current_scope` | 1 |  |
| `test_active_catalog_rows_use_lighter_green_and_reset_when_inactive` | 6 | scope, sort_order |
| `test_active_background_has_high_contrast_with_black_text` | 1 |  |

## tests/gui/test_checkbox_group.py

113 cases; 51 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_arming_the_cursor_neutralises_the_select_colour_on_every_row` | 1 | _no_display, monkeypatch |
| `test_arming_the_cursor_falls_back_to_tk_s_no_colour_form` | 1 | _no_display, monkeypatch |
| `test_the_cursor_tints_the_row_it_is_moved_to` | 1 | _no_display, monkeypatch |
| `test_the_tinted_row_carries_indicator_images_painted_on_the_tint` | 1 | _no_display, monkeypatch |
| `test_moving_the_cursor_reconfigures_the_row_it_leaves_and_the_row_it_lands_on` | 1 | _no_display, monkeypatch |
| `test_the_cursor_can_be_cleared` | 1 | _no_display, monkeypatch |
| `test_a_value_the_list_does_not_hold_clears_the_cursor_rather_than_raising` | 5 | _no_display, monkeypatch, value |
| `test_setting_the_cursor_where_it_already_is_configures_nothing` | 1 | _no_display, monkeypatch |
| `test_a_group_without_the_cursor_is_configured_exactly_as_it_is_today` | 1 | _no_display, monkeypatch |
| `test_a_row_is_drawn_from_its_left_edge_unless_the_group_asks_otherwise` | 1 | _no_display, monkeypatch |
| `test_the_rows_are_repainted_at_the_width_the_group_is_handed` | 1 | _no_display, monkeypatch |
| `test_a_rebuilt_group_is_armed_over_the_rows_it_now_holds` | 1 | _no_display, monkeypatch |
| `test_a_rebuild_that_replaces_the_list_drops_the_tint` | 1 | _no_display, monkeypatch |
| `test_a_group_that_never_armed_a_cursor_is_untouched_by_a_rebuild` | 1 | _no_display, monkeypatch |
| `test_replacing_the_options_arms_the_cursor_again` | 1 | _no_display, monkeypatch |
| `test_row_values_answers_with_the_string_every_row_holds` | 1 | _no_display, monkeypatch |
| `test_replacing_the_options_repaints_every_row` | 1 | _no_display, monkeypatch |
| `test_a_group_that_recorded_nothing_leaves_its_rows_alone` | 1 | _no_display, monkeypatch |
| `test_only_a_stretch_group_asks_guizero_to_fill_its_container` | 2 | _no_display, expected, monkeypatch, stretch |
| `test_a_stretch_group_hands_every_row_the_width_of_its_column` | 1 | _no_display, monkeypatch |
| `test_a_horizontal_stretch_group_weights_the_columns_its_rows_are_actually_in` | 1 | _no_display, monkeypatch |
| `test_a_group_that_did_not_ask_to_be_stretched_is_left_as_guizero_gridded_it` | 1 | _no_display, monkeypatch |
| `test_rebuilding_the_options_stretches_every_row_again` | 1 | _no_display, monkeypatch |
| `test_resizing_stretches_every_row_again` | 1 | _no_display, monkeypatch |
| `test_a_row_that_refuses_the_stretch_does_not_cost_the_others_theirs` | 1 | _no_display, monkeypatch |
| `test_only_a_named_row_is_held_off_the_row_above_it` | 1 | _no_display, monkeypatch |
| `test_a_row_that_no_longer_begins_a_block_loses_its_gap` | 1 | _no_display, monkeypatch |
| `test_the_leads_are_held_as_pixels_keyed_by_the_value_a_row_answers_with` | 1 | _no_display, monkeypatch |
| `test_the_gaps_can_be_asked_for_when_the_group_is_built` | 1 | _no_display, monkeypatch |
| `test_rebuilding_the_options_leads_every_row_again` | 1 | _no_display, monkeypatch |
| `test_resizing_leads_every_row_again` | 1 | _no_display, monkeypatch |
| `test_a_hidden_row_is_left_where_the_grid_forgot_it` | 1 | _no_display, monkeypatch |
| `test_a_group_that_named_no_rows_leaves_them_alone` | 1 | _no_display, monkeypatch |
| `test_a_row_that_refuses_its_gap_does_not_cost_the_others_theirs` | 1 | _no_display, monkeypatch |
| `test_setting_the_cursor_on_a_group_that_did_not_opt_in_does_nothing` | 1 | _no_display, monkeypatch |
| `test_the_painted_indicator_stays_off_the_rows_own_frame` | 22 | _no_display, monkeypatch, size, style |
| `test_a_ring_and_a_tick_box_are_drawn_at_one_size` | 11 | _no_display, monkeypatch, size |
| `test_the_painted_indicator_is_still_larger_than_the_text_beside_it` | 11 | _no_display, monkeypatch, size |
| `test_a_row_is_painted_with_a_square_indicator_of_that_size` | 2 | _no_display, monkeypatch, style |
| `test_the_indicator_cache_is_keyed_by_background` | 2 | _no_display, monkeypatch, style |
| `test_what_a_row_spends_before_its_text_is_its_indicator_and_a_fixed_margin` | 11 | _no_display, monkeypatch, size |
| `test_a_larger_row_spends_more_before_its_text_and_only_on_its_indicator` | 1 | _no_display, monkeypatch |
| `test_a_row_told_what_it_may_take_wraps_its_words_under_its_own_left_edge` | 1 | _no_display, monkeypatch |
| `test_a_row_that_was_given_no_wrap_is_given_no_justify_either` | 1 | _no_display, monkeypatch |
| `test_a_group_built_with_a_wrap_hands_it_to_every_row_it_ever_builds` | 1 | _no_display, monkeypatch |
| `test_a_list_that_already_fits_is_drawn_at_the_size_it_was_asked_for` | 1 | _no_display, monkeypatch |
| `test_a_list_that_does_not_fit_steps_down_to_the_largest_size_that_does` | 1 | _no_display, monkeypatch |
| `test_stepping_down_stops_at_the_floor_and_the_floor_is_the_answer` | 1 | _no_display, monkeypatch |
| `test_a_list_with_nothing_to_measure_keeps_the_size_it_was_asked_for` | 1 | _no_display, monkeypatch |
| `test_a_screen_that_cannot_be_measured_keeps_the_size_it_was_asked_for` | 5 | _no_display, monkeypatch, refusal |
| `test_a_row_is_measured_in_the_font_it_will_be_painted_in` | 1 | _no_display, monkeypatch |

## tests/gui/test_component_state_gui.py

7 cases; 7 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_invalid_initial_gui_raises` | 1 | monkeypatch, patch_gui_classes |
| `test_initial_gui_is_created_and_aggregator_set` | 1 | monkeypatch, patch_gui_classes |
| `test_screens_option_is_forwarded_to_gui_instances` | 1 | monkeypatch, patch_gui_classes |
| `test_cycle_gui_switches_and_closes_previous` | 1 | monkeypatch, patch_gui_classes |
| `test_cycle_gui_ignores_unknown_key` | 1 | monkeypatch, patch_gui_classes |
| `test_cycle_gui_switch_back_and_forth_uses_gui_thread_close_path` | 1 | monkeypatch, patch_gui_classes |
| `test_guis_property_lists_expected_entries` | 1 | monkeypatch, patch_gui_classes |

## tests/gui/test_controller_view.py

160 cases; 60 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_non_throttle_slider_levels_use_host_digital_font` | 1 | controller_view, monkeypatch |
| `test_the_provisional_size_is_capped_by_both_dimensions_of_the_cell` | 1 |  |
| `test_the_slider_box_lands_on_exactly_four_button_heights` | 8 | button_size, title_overhead |
| `test_slider_length_never_drops_below_one_pixel` | 1 |  |
| `test_slider_length_ignores_a_negative_overhead_rather_than_trusting_it` | 1 |  |
| `test_aux_row_gets_whatever_is_left_below_the_fixed_slider_row` | 1 |  |
| `test_aux_row_never_drops_below_one_pixel` | 1 |  |
| `test_the_slider_row_lands_on_the_keypads_real_fourth_row_bottom` | 1 |  |
| `test_slider_row_alignment_never_drops_below_one_pixel` | 1 |  |
| `test_the_horn_is_bigger_than_the_bell_because_it_has_no_label_above_it` | 1 |  |
| `test_each_button_fills_the_height_of_its_own_half_of_the_row` | 1 |  |
| `test_a_shared_width_overflow_comes_off_both_buttons` | 1 |  |
| `test_the_sizes_never_drop_below_a_usable_touch_target` | 1 |  |
| `test_negative_insets_are_ignored_rather_than_trusted` | 1 |  |
| `test_the_model_reproduces_both_devices` | 2 | expected, name, parent_width, row_height |
| `test_the_freight_bell_is_an_image_asset_that_exists` | 1 |  |
| `test_no_bell_codepoint_is_used_as_a_button_label` | 1 |  |
| `test_the_provisional_size_and_the_correction_are_both_wired_up` | 1 |  |
| `test_the_slider_box_sizing_helpers_are_both_wired_up` | 1 |  |
| `test_the_keypad_alignment_helper_is_wired_up` | 1 |  |
| `test_the_rr_speed_box_has_no_align_that_a_later_show_would_reapply` | 1 |  |
| `test_the_rr_speed_box_does_not_rely_on_a_sticky_override` | 1 |  |
| `test_the_rr_speed_button_is_centered_in_the_free_space` | 1 |  |
| `test_the_rr_speed_button_now_sits_inside_a_titled_speed_limit_box` | 1 |  |
| `test_the_rr_speed_titlebox_is_also_centered_in_the_free_space` | 1 |  |
| `test_the_fit_gives_the_horn_the_labels_height_and_the_bell_its_own` | 1 |  |
| `test_the_fit_measures_the_column_not_the_cell` | 1 |  |
| `test_the_fit_leaves_a_pair_that_already_fits_untouched` | 1 |  |
| `test_the_fit_refuses_to_measure_a_cell_that_is_not_laid_out_yet` | 1 |  |
| `test_the_fit_never_shrinks_below_a_usable_touch_target` | 1 |  |
| `test_the_fit_ignores_chrome_that_measures_impossibly` | 1 |  |
| `test_the_fit_survives_a_pair_that_has_gone_away` | 1 |  |
| `test_nothing_is_fitted_before_the_pair_has_been_built` | 1 |  |
| `test_the_backstop_takes_a_residual_overflow_off_the_horn` | 1 |  |
| `test_the_backstop_leaves_the_bell_alone` | 1 |  |
| `test_no_backstop_when_the_row_already_fits` | 1 |  |
| `test_the_trim_is_the_measured_shortfall` | 1 |  |
| `test_only_a_compact_pane_shrinks_the_pairs_title` | 1 |  |
| `test_the_compact_title_is_smaller_than_the_default_it_replaces` | 1 |  |
| `test_the_horn_is_given_a_visible_relief` | 1 |  |
| `test_the_horn_config_and_the_title_size_are_both_wired_up` | 1 |  |
| `test_the_trim_never_leaves_the_horn_smaller_than_the_bell` | 1 |  |
| `test_the_trim_still_respects_the_touch_target_floor` | 1 |  |
| `test_the_direction_keys_are_given_a_border_to_carry_their_color` | 1 |  |
| `test_no_other_engine_op_key_wears_a_border` | 1 |  |
| `test_a_row_with_a_spare_button_of_width_gets_the_extra_column` | 1 |  |
| `test_a_row_already_spoken_for_does_not` | 1 |  |
| `test_the_column_has_to_fit_whole` | 1 |  |
| `test_a_measurement_that_has_not_settled_yet_gets_no_column` | 12 | reading, unmeasured |
| `test_the_fit_test_is_wired_up` | 1 |  |
| `test_the_extra_column_is_created_before_the_sliders` | 1 |  |
| `test_the_extra_column_holds_its_place_when_its_keys_hide` | 1 |  |
| `test_a_row_with_no_room_loses_the_box_without_repacking_its_neighbors` | 1 |  |
| `test_every_button_in_the_extra_column_is_an_alias_of_a_real_command` | 1 |  |
| `test_extra_column_visibility_for_each_equipment_type` | 72 | engine_type, previous_type |
| `test_acela_retains_main_keypad_and_popup_power_keys` | 4 | command, wide |
| `test_extra_column_does_not_change_main_keypad_visibility` | 8 | engine_type |
| `test_the_extra_column_inherits_the_holds_of_the_buttons_it_copies` | 1 |  |
| `test_a_hold_is_only_copied_onto_a_button_that_was_built` | 1 |  |
| `test_the_info_row_can_be_asked_for_by_name_so_its_height_can_be_reserved` | 1 |  |

## tests/gui/test_dummy_gui_components.py

6 cases; 6 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_scale_calculation` | 1 | instance, monkeypatch, patch_guizero_and_system |
| `test_on_sync_starts_and_subscribes` | 1 | monkeypatch, patch_guizero_and_system |
| `test_run_builds_min_ui_and_sync_state` | 1 | monkeypatch, patch_guizero_and_system |
| `test_toggle_power_on_path` | 1 | monkeypatch, patch_guizero_and_system |
| `test_toggle_power_off_path` | 1 | monkeypatch, patch_guizero_and_system |
| `test_set_lights_icons_and_klaxon_off` | 1 | monkeypatch, patch_guizero_and_system |

## tests/gui/test_editable_text.py

75 cases; 44 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_desktop_uses_native_entry_and_enter_commits` | 8 | desktop, editable_text_module, editor, enter_key, monkeypatch, original, replacement |
| `test_desktop_escape_cancels_and_entry_can_be_reopened` | 4 | desktop, editable_text_module, editor, monkeypatch |
| `test_desktop_native_input_keeps_length_limit_and_commits_on_focus_loss` | 4 | desktop, editable_text_module, editor, monkeypatch |
| `test_explicit_keyboard_preference_overrides_platform_default` | 6 | editable_text_module, monkeypatch, platform_name, show_keyboard |
| `test_hold_begins_inline_edit` | 1 | editable_text_module, monkeypatch |
| `test_editable_false_makes_text_ignore_hold` | 1 | editable_text_module, monkeypatch |
| `test_editable_true_enables_hold_to_edit` | 1 | editable_text_module, monkeypatch |
| `test_editable_true_without_editor_raises_unsupported_mode` | 1 | editable_text_module, monkeypatch |
| `test_release_before_hold_cancels_inline_edit` | 1 | editable_text_module, monkeypatch |
| `test_leave_does_not_cancel_hold_by_default` | 1 | editable_text_module, monkeypatch |
| `test_leave_can_cancel_hold_when_configured` | 1 | editable_text_module, monkeypatch |
| `test_added_hold_target_can_begin_edit` | 1 | editable_text_module, monkeypatch |
| `test_commit_cancels_pending_keyboard_launch` | 1 | editable_text_module, monkeypatch |
| `test_builtin_keyboard_is_shown_and_inserts_text` | 1 | editable_text_module, monkeypatch |
| `test_editor_commit_label_defaults_to_save_and_can_be_customized` | 12 | compact, editable_text_module, editor, label, monkeypatch, options |
| `test_builtin_keyboard_supports_lower_upper_and_symbols` | 1 | editable_text_module, monkeypatch |
| `test_builtin_keyboard_moves_cursor_and_del_deletes_left` | 1 | editable_text_module, monkeypatch |
| `test_builtin_keyboard_enforces_max_length_on_touch_input` | 1 | editable_text_module, monkeypatch |
| `test_keypad_editor_shows_number_pad_and_enforces_max_length` | 1 | editable_text_module, monkeypatch |
| `test_choices_editor_commits_choice_keys_and_keeps_display_text` | 3 | editable_text_module, monkeypatch, platform_name |
| `test_choices_editor_current_button_restores_original_selection` | 1 | editable_text_module, monkeypatch |
| `test_choices_editor_arrow_buttons_move_selection` | 1 | editable_text_module, monkeypatch |
| `test_choices_editor_arrow_buttons_use_native_button_repeat` | 1 | editable_text_module, monkeypatch |
| `test_choices_editor_allows_configurable_visible_rows` | 1 | editable_text_module, monkeypatch |
| `test_commit_updates_value_truncates_and_invokes_callback` | 1 | editable_text_module, monkeypatch |
| `test_cancel_restores_original_value` | 1 | editable_text_module, monkeypatch |
| `test_a_compact_editor_is_a_panel_in_the_app_window_not_a_window_of_its_own` | 1 | editable_text_module, monkeypatch |
| `test_the_compact_keyboard_spans_the_display_and_drops_out_of_the_field` | 1 | editable_text_module, monkeypatch |
| `test_the_compact_keypad_takes_only_the_pane_that_owns_the_field` | 1 | editable_text_module, monkeypatch |
| `test_the_compact_chooser_takes_one_pane_and_is_centered_in_it` | 1 | editable_text_module, monkeypatch |
| `test_a_pane_editor_follows_the_field_to_the_right_hand_pane` | 1 | editable_text_module, monkeypatch |
| `test_a_compact_editor_is_built_before_it_is_placed` | 1 | editable_text_module, monkeypatch |
| `test_a_compact_editor_is_clamped_to_the_room_below_the_field` | 1 | editable_text_module, monkeypatch |
| `test_portrait_editor_geometry_is_untouched` | 1 | editable_text_module, monkeypatch |
| `test_portrait_sizes_the_window_before_filling_it` | 1 | editable_text_module, monkeypatch |
| `test_a_compact_editor_is_measured_against_the_app_window_not_the_screen` | 1 | editable_text_module, monkeypatch |
| `test_a_compact_editor_flips_above_a_field_with_no_room_beneath_it` | 1 | editable_text_module, monkeypatch |
| `test_compact_keys_are_smaller_than_portrait_keys` | 1 | editable_text_module, monkeypatch |
| `test_the_shrink_applies_to_widget_sizes_and_not_to_portrait_geometry` | 1 | editable_text_module, monkeypatch |
| `test_a_compact_chooser_names_the_field_it_is_editing` | 1 | editable_text_module, monkeypatch |
| `test_a_portrait_chooser_keeps_its_original_heading` | 1 | editable_text_module, monkeypatch |
| `test_a_compact_chooser_with_no_field_name_falls_back` | 1 | editable_text_module, monkeypatch |
| `test_an_open_chooser_reports_itself_and_moves_on_request` | 1 | editable_text_module, monkeypatch |
| `test_a_text_field_is_never_reported_as_choosing` | 1 | editable_text_module, monkeypatch |

## tests/gui/test_engine_gui_accessories.py

60 cases; 48 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_configured_accessory_providers_are_isolated_per_engine_gui` | 1 |  |
| `test_get_configured_accessory_caches_adapter_and_activates_tmcc` | 1 |  |
| `test_get_configured_accessory_caches_none_when_no_adapter` | 1 |  |
| `test_get_accessory_view_builds_overlay_once_and_caches` | 1 |  |
| `test_set_accessory_view_allows_explicit_none` | 1 |  |
| `test_on_new_accessory_calls_update_ac_status_for_asc2` | 1 | monkeypatch |
| `test_on_new_accessory_updates_sensor_track_value` | 1 | monkeypatch |
| `test_on_new_accessory_updates_amc2_panel` | 1 | monkeypatch |
| `test_reload_configured_accessories_reindexes_and_restarts_prewarm` | 1 | monkeypatch |
| `test_reload_configured_accessories_resets_catalog_panel_when_it_exists` | 1 | monkeypatch |
| `test_reload_configured_accessories_removes_only_deleted_configured_accessory_options` | 1 | monkeypatch |
| `test_reload_configured_accessories_resets_active_overlay_to_acc_entry` | 1 | monkeypatch |
| `test_reload_configured_accessories_failure_leaves_existing_caches` | 1 | monkeypatch |
| `test_accessory_config_signature_tracks_file_changes` | 1 | tmp_path, tmp_path_factory |
| `test_accessory_config_change_debounces_and_schedules_apply` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_accessory_config_change_load_failure_keeps_current_set` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_input_contexts_follow_the_accessory_panel_displayed` | 4 | expected, kind |
| `test_input_contexts_are_empty_where_no_accessory_context_is_defined` | 2 | kind |
| `test_input_contexts_are_empty_with_nothing_selected` | 1 |  |
| `test_input_contexts_report_bpc2_for_a_train_scope_power_district` | 1 |  |
| `test_input_contexts_do_not_consult_the_panel_when_a_switch_or_route_is_shown` | 1 |  |
| `test_show_generic_acc_panel_forces_the_generic_panel_and_re_enters_ops_mode` | 1 |  |
| `test_show_native_acc_panel_drops_the_override_and_re_enters_ops_mode` | 1 |  |
| `test_ops_mode_with_generic_override_does_not_reopen_configured_overlay` | 1 | monkeypatch |
| `test_ops_mode_without_override_opens_configured_overlay` | 1 | monkeypatch |
| `test_native_return_restores_configured_overlay` | 1 | monkeypatch |
| `test_ops_mode_generic_override_on_unconfigured_id_leaves_generic_panel` | 1 | monkeypatch |
| `test_the_pad_follows_a_forced_generic_panel` | 1 |  |
| `test_acc_base_context_claims_what_it_does_not_bind` | 1 |  |
| `test_on_acc_speed_command_sends_a_clamped_relative_step` | 6 | expected, value |
| `test_on_lcs_command_sends_the_same_thing_the_on_and_off_keys_do` | 2 | monkeypatch, on |
| `test_on_lcs_command_sends_nothing_with_nothing_selected` | 1 | monkeypatch |
| `test_on_asc2_momentary_delegates_to_the_keypad` | 2 | pressed |
| `test_on_sensor_track_step_moves_the_cursor_and_writes_nothing` | 2 | delta |
| `test_on_sensor_track_step_answers_false_where_the_highlight_did_not_move` | 1 |  |
| `test_on_sensor_track_select_writes_the_highlighted_option_at_this_pane_s_id` | 1 |  |
| `test_a_select_writes_the_option_under_the_cursor_and_moves_the_dot_onto_it` | 1 |  |
| `test_on_sensor_track_select_with_nothing_highlighted_writes_nothing` | 1 |  |
| `test_a_second_select_records_the_option_it_displaced` | 1 |  |
| `test_selecting_the_option_already_showing_keeps_the_undo_point` | 1 |  |
| `test_on_sensor_track_revert_puts_back_the_option_the_last_select_replaced` | 1 |  |
| `test_a_revert_is_one_shot_rather_than_a_way_of_flipping_between_two_options` | 1 |  |
| `test_a_revert_with_nothing_selected_yet_abandons_the_stepping_and_sends_nothing` | 1 |  |
| `test_a_revert_on_a_pane_re_scoped_to_another_sensor_track_writes_nothing` | 1 |  |
| `test_on_new_accessory_seeds_what_a_revert_falls_back_to` | 1 |  |
| `test_a_report_for_the_same_track_moves_the_dot_and_leaves_a_step_in_progress_alone` | 1 |  |
| `test_a_report_for_a_different_track_re_seeds_the_cursor` | 1 |  |
| `test_a_track_with_no_report_leaves_nothing_to_point_at` | 1 |  |

## tests/gui/test_engine_gui_create.py

73 cases; 27 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_creating_a_component_initializes_it_and_selects_it` | 3 | monkeypatch, scope |
| `test_creating_over_an_existing_state_reuses_it_without_reinitializing` | 1 | monkeypatch |
| `test_a_component_is_not_provisional_until_it_is_created` | 1 |  |
| `test_the_provisional_flag_is_per_scope_and_per_id` | 1 | monkeypatch |
| `test_a_provisional_selection_stays_out_of_recents` | 1 |  |
| `test_a_defined_selection_still_reaches_recents` | 1 |  |
| `test_a_provisional_selection_still_enters_ops_mode_when_it_is_not_there_yet` | 1 |  |
| `test_deleting_a_state_drops_its_provisional_entry` | 1 |  |
| `test_ids_in_range_are_creatable` | 15 | scope, tmcc_id |
| `test_ids_out_of_range_are_not_creatable` | 15 | scope, tmcc_id |
| `test_non_creatable_scopes_are_rejected_at_every_id` | 2 | scope |
| `test_engines_are_deliberately_out_of_scope_for_now` | 1 |  |
| `test_enter_on_an_undefined_creatable_id_creates_and_operates` | 3 | scope |
| `test_enter_on_an_undefined_non_creatable_id_still_returns_to_entry_mode` | 2 | scope |
| `test_enter_on_an_out_of_range_id_still_returns_to_entry_mode` | 9 | scope, tmcc_id |
| `test_enter_on_a_defined_id_takes_the_unchanged_fast_path` | 3 | scope |
| `test_the_set_key_create_path_is_unchanged` | 1 | monkeypatch |
| `test_promoting_a_provisional_record_adds_it_to_recents_options_and_catalog` | 3 | scope |
| `test_promoting_something_that_was_never_provisional_does_nothing` | 1 |  |
| `test_promoting_the_same_record_twice_only_counts_once` | 1 |  |
| `test_promoting_without_a_state_falls_back_to_the_active_one` | 1 |  |
| `test_promoting_with_nothing_selected_is_a_no_op` | 1 |  |
| `test_an_empty_record_is_not_promoted_while_the_base_is_still_silent` | 1 |  |
| `test_a_record_the_base_has_answered_for_is_promoted_without_an_edit` | 1 |  |
| `test_promote_if_populated_tolerates_nothing_selected` | 1 |  |
| `test_an_incoming_switch_report_promotes_a_provisional_switch` | 1 |  |
| `test_an_incoming_accessory_report_promotes_a_provisional_accessory` | 1 |  |

## tests/gui/test_engine_gui_transitions.py

34 cases; 34 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_show_scope_catalog_holds_current_scope_button` | 1 |  |
| `test_show_scope_catalog_closes_catalog_when_already_visible` | 1 |  |
| `test_hide_scope_catalog_noop_when_not_visible` | 1 |  |
| `test_catalog_visible_reflects_panel_state` | 1 |  |
| `test_select_catalog_entry_delegates_when_panel_visible` | 1 |  |
| `test_select_catalog_entry_noop_when_panel_hidden` | 1 |  |
| `test_scroll_catalog_delegates_when_panel_visible` | 1 |  |
| `test_scroll_catalog_noop_when_panel_hidden` | 1 |  |
| `test_scroll_catalog_to_end_jumps_highlight_without_selecting` | 1 |  |
| `test_scroll_catalog_to_end_noop_when_panel_hidden` | 1 |  |
| `test_popup_visible_reflects_popup_manager_state` | 1 |  |
| `test_close_popup_closes_when_popup_visible` | 1 |  |
| `test_close_popup_noop_when_no_popup_visible` | 1 |  |
| `test_update_component_info_with_state_updates_ui_and_ops_mode` | 1 |  |
| `test_update_component_info_without_state_uses_not_found_and_scoped_callback` | 1 |  |
| `test_update_component_info_repaints_hidden_image_when_returning_to_ops_mode` | 1 |  |
| `test_update_component_info_zero_clears_image_and_resets_keystroke_flag` | 1 |  |
| `test_a_panel_that_would_not_close_stops_the_pane_re_aiming_itself_underneath_it` | 1 |  |
| `test_promoting_a_module_the_base_had_never_heard_of_does_not_ask_the_panel_to_go` | 1 |  |
| `test_a_scope_press_asks_the_panel_to_go` | 1 |  |
| `test_the_keys_that_walk_through_recents_ask_the_panel_to_go` | 1 |  |
| `test_a_forced_accessory_panel_does_not_outlive_a_change_of_selection` | 1 |  |
| `test_a_forced_accessory_panel_does_not_survive_a_scope_press` | 1 |  |
| `test_update_component_info_accessory_uses_configured_accessory_name` | 1 | monkeypatch |
| `test_monitor_state_reuses_existing_watcher_and_replaces_on_tmcc_change` | 1 | monkeypatch |
| `test_on_new_train_builds_train_link_queue_and_sets_engine_scope_tmcc` | 1 |  |
| `test_on_scope_switches_between_engine_and_train_without_forcing_entry_mode` | 1 |  |
| `test_on_new_engine_marks_train_scope_when_train_linked_engine_is_active` | 1 | monkeypatch |
| `test_on_info_unbinds_long_press_and_close_handler_rebinds` | 1 |  |
| `test_update_component_info_same_selection_skips_redundant_ops_mode_and_image_refresh` | 1 |  |
| `test_on_scope_rebuilds_options_once_for_scope_transition` | 1 |  |
| `test_clear_record_clears_state_without_notifying_and_queues_cache_rebuild` | 1 |  |
| `test_delete_callback_queues_cache_rebuild_for_component_state` | 1 | monkeypatch |
| `test_delete_callback_ignores_events_after_shutdown` | 1 | monkeypatch |

## tests/gui/test_gui_checkpoint.py

65 cases; 46 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_each_state_flag_resolves_to_its_own_panel` | 5 | _patch_widgets, expected, flags, monkeypatch |
| `test_the_more_specific_panel_wins_where_flags_overlap` | 4 | _patch_widgets, expected, flags, monkeypatch |
| `test_an_unrecognised_lcs_port_falls_through_to_the_generic_panel` | 1 | _patch_widgets, monkeypatch |
| `test_no_panel_is_reported_off_an_accessory_screen` | 1 | _patch_widgets, monkeypatch |
| `test_a_state_that_is_not_an_accessory_at_all_reports_no_panel` | 1 | _patch_widgets, monkeypatch |
| `test_a_train_scope_power_district_reports_the_bpc2_panel` | 1 | _patch_widgets, monkeypatch |
| `test_a_configured_accessory_adapter_is_unwrapped_before_the_flags_are_read` | 1 | _patch_widgets, monkeypatch |
| `test_the_panel_kind_may_be_asked_about_a_state_that_is_not_the_active_one` | 1 | _patch_widgets, monkeypatch |
| `test_route_ops_mode_shows_the_fire_key_alone` | 1 | _patch_widgets, monkeypatch |
| `test_switch_ops_mode_shows_thru_and_out_and_nothing_else` | 1 | _patch_widgets, monkeypatch |
| `test_the_switch_screen_carries_its_own_set_and_info_keys` | 1 | _patch_widgets, monkeypatch |
| `test_generic_accessory_ops_mode_expands_the_aux_keys_and_shows_the_throttle` | 1 | _patch_widgets, monkeypatch |
| `test_generic_accessory_ops_mode_rebinds_the_number_keys_to_accessory_commands` | 1 | _patch_widgets, monkeypatch |
| `test_the_number_keys_start_out_bound_to_the_keypad` | 1 | _patch_widgets, monkeypatch |
| `test_bpc2_ops_mode_shows_on_status_and_off` | 1 | _patch_widgets, monkeypatch |
| `test_asc2_ops_mode_adds_the_momentary_aux1_key_to_the_bpc2_set` | 1 | _patch_widgets, monkeypatch |
| `test_each_lcs_panel_carries_a_key_to_the_generic_panel` | 1 | _patch_widgets, monkeypatch |
| `test_entry_mode_collapses_the_fourth_column` | 1 | _patch_widgets, monkeypatch |
| `test_route_ops_mode_collapses_the_fourth_column` | 1 | _patch_widgets, monkeypatch |
| `test_switch_ops_mode_expands_the_fourth_column` | 1 | _patch_widgets, monkeypatch |
| `test_generic_accessory_ops_mode_expands_the_fourth_column` | 1 | _patch_widgets, monkeypatch |
| `test_the_bpc2_panel_collapses_the_fourth_column` | 1 | _patch_widgets, monkeypatch |
| `test_the_asc2_panel_expands_the_fourth_column` | 1 | _patch_widgets, monkeypatch |
| `test_returning_to_entry_recollapses_the_fourth_column` | 1 | _patch_widgets, monkeypatch |
| `test_sensor_track_ops_mode_replaces_the_keypad_with_the_sequence_box` | 1 | _patch_widgets, monkeypatch |
| `test_amc2_ops_mode_replaces_the_keypad_with_the_amc2_box` | 1 | _patch_widgets, monkeypatch |
| `test_a_configured_accessory_puts_the_overlay_key_in_the_free_generic_slot` | 1 | _patch_widgets, monkeypatch |
| `test_a_configured_accessory_on_an_asc2_panel_moves_the_overlay_key` | 1 | _patch_widgets, monkeypatch |
| `test_the_aux_keys_carry_the_grids_the_collapse_and_expand_move_them_between` | 1 | _patch_widgets, monkeypatch |
| `test_expanding_and_collapsing_moves_only_the_cells_with_both_grids` | 1 | _patch_widgets, monkeypatch |
| `test_entry_mode_shows_the_entry_cells_and_hides_every_ops_cell` | 1 | _patch_widgets, monkeypatch |
| `test_entry_mode_clears_the_component_info_by_default` | 1 | _patch_widgets, monkeypatch |
| `test_entry_mode_hides_the_set_key_for_a_route_and_enables_reset_for_an_engine` | 1 | _patch_widgets, monkeypatch |
| `test_enter_ops_mode_base_hides_both_cell_sets_and_collapses_the_aux_keys` | 1 | _patch_widgets, monkeypatch |
| `test_scope_keypad_forces_entry_mode_where_nothing_is_selected` | 1 | _patch_widgets, monkeypatch |
| `test_scope_keypad_leaves_a_selected_component_in_ops_mode` | 1 | _patch_widgets, monkeypatch |
| `test_enter_on_an_unknown_id_returns_to_entry_mode_in_every_scope` | 2 | _patch_widgets, monkeypatch, scope |
| `test_enter_on_an_unknown_id_creates_a_provisional_component` | 3 | _patch_widgets, monkeypatch, scope |
| `test_enter_on_a_known_id_enters_ops_mode` | 5 | _patch_widgets, monkeypatch, tmcc_id |
| `test_each_panel_claims_the_pad_through_the_shared_chain_table` | 6 | _patch_widgets, expected, kind, monkeypatch |
| `test_an_accessory_scope_with_nothing_selected_claims_nothing` | 1 | _patch_widgets, monkeypatch |
| `test_a_selected_switch_and_route_claim_their_own_contexts` | 1 | _patch_widgets, monkeypatch |
| `test_an_unselected_switch_or_route_claims_nothing` | 1 | _patch_widgets, monkeypatch |
| `test_an_engine_panel_remaps_nothing` | 1 | _patch_widgets, monkeypatch |
| `test_a_power_district_in_train_scope_claims_the_bpc2_chain` | 1 | _patch_widgets, monkeypatch |
| `test_the_screen_and_the_pad_read_the_same_property` | 1 | _patch_widgets, monkeypatch |

## tests/gui/test_gui_deck_parity.py

52 cases; 26 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_the_compact_pane_bounds_the_info_box_and_the_portrait_one_does_not` | 1 | _patch_widgets, monkeypatch |
| `test_the_sequence_rows_are_padded_more_tightly_on_the_pane` | 1 | _patch_widgets, monkeypatch |
| `test_the_pane_clamps_the_image_box_and_portrait_takes_what_it_is_given` | 1 | _patch_widgets, monkeypatch |
| `test_every_new_cell_lands_in_the_same_slot_on_the_pane_as_in_portrait` | 2 | _patch_widgets, compact, monkeypatch |
| `test_the_new_cells_are_ops_cells_on_the_pane_too` | 2 | _patch_widgets, compact, monkeypatch |
| `test_the_sensor_track_panel_has_no_generic_toggle_on_the_pane` | 2 | _patch_widgets, compact, monkeypatch |
| `test_the_amc2_nav_keys_are_wired_on_the_pane_too` | 2 | _patch_widgets, compact, monkeypatch |
| `test_the_configured_overlay_key_is_sized_from_the_pane_button_size` | 2 | _patch_widgets, compact, monkeypatch |
| `test_the_way_back_from_a_forced_generic_panel_wears_the_device_icon` | 2 | _patch_widgets, compact, monkeypatch |
| `test_the_way_back_wears_the_configured_accessory_icon_on_the_pane` | 2 | _patch_widgets, compact, monkeypatch |
| `test_entry_collapses_the_fourth_column_on_the_pane` | 2 | _patch_widgets, compact, monkeypatch |
| `test_switch_ops_expands_the_fourth_column_on_the_pane` | 2 | _patch_widgets, compact, monkeypatch |
| `test_generic_accessory_ops_expands_both_extra_columns_on_the_pane` | 2 | _patch_widgets, compact, monkeypatch |
| `test_the_bpc2_panel_collapses_the_fourth_column_on_the_pane` | 2 | _patch_widgets, compact, monkeypatch |
| `test_the_shared_lcs_key_sits_in_column_zero_on_bpc2_on_the_pane` | 2 | _patch_widgets, compact, monkeypatch |
| `test_the_switch_screen_stacks_the_shared_lcs_key_under_its_set_key_on_the_pane` | 2 | _patch_widgets, compact, monkeypatch |
| `test_the_asc2_panel_expands_the_fourth_column_on_the_pane` | 2 | _patch_widgets, compact, monkeypatch |
| `test_the_pad_width_tightens_to_the_occupied_columns_on_the_pane` | 2 | _patch_widgets, compact, monkeypatch |
| `test_returning_to_entry_recollapses_the_fourth_column_on_the_pane` | 2 | _patch_widgets, compact, monkeypatch |
| `test_the_footer_button_did_not_disturb_the_cursor_stepping` | 2 | _patch_widgets, compact, monkeypatch |
| `test_the_cursor_still_clamps_at_both_ends_of_the_ten_rows` | 4 | _patch_widgets, compact, delta, monkeypatch, start |
| `test_the_dot_and_the_cursor_stay_separate_things` | 2 | _patch_widgets, compact, monkeypatch |
| `test_a_pane_hosted_gui_roots_itself_in_its_pane` | 1 | _patch_widgets, monkeypatch |
| `test_creation_works_the_same_hosted_in_a_pane` | 4 | _patch_widgets, monkeypatch, pane, scope |
| `test_promotion_works_the_same_hosted_in_a_pane` | 2 | _patch_widgets, monkeypatch, pane |
| `test_the_panel_toggles_work_the_same_hosted_in_a_pane` | 2 | _patch_widgets, monkeypatch, pane |

## tests/gui/test_guizero_base.py

47 cases; 37 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_run_clears_local_app_reference_from_shutdown_closure` | 1 | _patch_runtime, monkeypatch |
| `test_scaled_image_dimensions_never_reach_zero` | 1 | _patch_runtime, monkeypatch |
| `test_compact_prepared_image_preserves_source_aspect_ratio` | 1 | _patch_runtime, monkeypatch |
| `test_nothing_preserves_a_pictures_proportions_unless_a_host_asks_for_it` | 1 | _patch_runtime, monkeypatch |
| `test_a_short_strip_stretches_the_engine_picture_unless_the_host_says_otherwise` | 1 | _patch_runtime, monkeypatch |
| `test_a_strip_tall_enough_for_the_picture_costs_the_host_nothing_to_ask` | 1 | _patch_runtime, monkeypatch |
| `test_an_accessory_photo_fills_the_height_it_is_given_either_way` | 1 | _patch_runtime, monkeypatch |
| `test_a_host_that_asks_keeps_the_proportions_of_a_prepared_image_too` | 1 | _patch_runtime, monkeypatch |
| `test_button_divisor_supports_compact_landscape_controls` | 1 | _patch_runtime, monkeypatch |
| `test_the_colored_border_scales_with_the_display_within_bounds` | 4 | _patch_runtime, expected, monkeypatch, scale_by |
| `test_the_hover_background_goes_through_the_widget_so_a_border_can_follow_it` | 1 | _patch_runtime, monkeypatch |
| `test_the_hover_color_is_set_after_the_face_it_would_be_overwritten_by` | 1 | _patch_runtime, monkeypatch |
| `test_a_button_carrying_a_colored_border_keeps_it` | 1 | _patch_runtime, monkeypatch |
| `test_every_other_button_keeps_the_plain_outline_it_has_always_worn` | 2 | _patch_runtime, border_thickness, monkeypatch |
| `test_poll_shutdown_processes_up_to_five_messages_per_tick` | 1 | _patch_runtime, monkeypatch |
| `test_poll_shutdown_logs_callback_exception_and_continues` | 1 | _patch_runtime, caplog, monkeypatch |
| `test_submit_request_sends_on_worker_thread_with_repeat_and_delay` | 1 | _patch_runtime, monkeypatch |
| `test_get_prod_info_does_not_requeue_callback_while_future_pending` | 1 | _patch_runtime, monkeypatch |
| `test_request_prod_info_returns_na_when_lookup_unavailable` | 1 | _patch_runtime, monkeypatch |
| `test_popup_manager_close_invokes_overlay_close_hook` | 1 | _patch_runtime, monkeypatch |
| `test_resolve_font_family_accepts_embedded_family_name` | 1 | _patch_runtime, monkeypatch |
| `test_resolve_font_family_uses_readable_fallback` | 1 | _patch_runtime, monkeypatch |
| `test_installed_digital_font_takes_priority_over_the_bundle` | 3 | _patch_runtime, family, monkeypatch |
| `test_bundled_font_is_checked_even_when_tk_caches_its_family_list` | 1 | _patch_runtime, monkeypatch |
| `test_bundled_font_never_returns_a_silently_substituted_font` | 2 | _patch_runtime, caplog, monkeypatch, registered |
| `test_font_lookup_does_not_register_unless_requested_for_digital_dream` | 2 | _patch_runtime, load_bundled, monkeypatch, preferred |
| `test_tk_font_errors_use_the_default_font` | 2 | _patch_runtime, monkeypatch, operation |
| `test_font_lookup_preserves_cancellation` | 2 | _patch_runtime, error, monkeypatch |
| `test_get_image_honors_the_requested_size_on_a_cache_hit` | 1 | _patch_runtime, monkeypatch, tmp_path, tmp_path_factory |
| `test_get_image_still_caches_a_repeated_identical_request` | 1 | _patch_runtime, monkeypatch, tmp_path, tmp_path_factory |
| `test_get_image_treats_an_int_size_and_a_square_tuple_as_one_entry` | 1 | _patch_runtime, monkeypatch, tmp_path, tmp_path_factory |
| `test_get_image_separates_entries_that_differ_only_by_flag` | 1 | _patch_runtime, monkeypatch, tmp_path, tmp_path_factory |
| `test_get_scaled_image_emits_no_stdout` | 1 | _patch_runtime, capsys, monkeypatch |
| `test_hidden_keypad_image_cell_defers_decode_until_first_shown` | 1 | _patch_runtime, monkeypatch |
| `test_hidden_keypad_image_cell_decodes_when_revealed_via_visible_setter` | 1 | _patch_runtime, monkeypatch |
| `test_hidden_keypad_image_cell_decodes_from_original_path_after_image_reassigned` | 1 | _patch_runtime, monkeypatch |
| `test_visible_keypad_image_cell_decodes_during_build` | 1 | _patch_runtime, monkeypatch |

## tests/gui/test_hold_button.py

67 cases; 66 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_press_event_does_not_start_progress_when_disabled` | 1 |  |
| `test_press_event_starts_progress_and_hold_timer_when_enabled` | 1 |  |
| `test_progress_does_not_start_when_disabled` | 1 |  |
| `test_progress_starts_when_enabled` | 1 |  |
| `test_progress_tick_stops_existing_progress_when_disabled` | 1 |  |
| `test_progress_tick_updates_and_reschedules_when_enabled` | 1 |  |
| `test_hover_enter_does_not_paint_disabled_button` | 1 |  |
| `test_hover_enter_and_leave_paint_enabled_button` | 1 |  |
| `test_flash_press_does_not_paint_disabled_button` | 1 |  |
| `test_flash_press_paints_enabled_button` | 1 |  |
| `test_begin_hold_starts_the_same_hold_a_finger_would` | 1 |  |
| `test_cancel_hold_stops_progress_without_firing_the_short_press` | 1 |  |
| `test_a_crossing_still_inside_the_button_is_discarded_outright` | 1 |  |
| `test_jitter_canceled_by_a_following_enter_does_not_abort_the_hold` | 1 |  |
| `test_dragging_off_the_button_cancels_once_the_leave_persists` | 1 |  |
| `test_a_persisting_leave_whose_pointer_is_back_inside_does_not_cancel` | 1 |  |
| `test_unreadable_pointer_position_does_not_cancel` | 1 |  |
| `test_a_leave_is_ignored_when_no_hold_is_in_flight` | 1 |  |
| `test_cancel_hold_always_cancels_regardless_of_the_pointer` | 1 |  |
| `test_slop_is_wide_enough_to_absorb_touch_wander` | 1 |  |
| `test_a_crossing_just_outside_the_widget_is_still_treated_as_inside` | 1 |  |
| `test_pointer_outside_allows_slop_around_the_edges` | 1 |  |
| `test_overlay_is_placed_once_while_the_geometry_is_unchanged` | 1 |  |
| `test_overlay_is_re_placed_after_it_has_been_hidden` | 1 |  |
| `test_a_state_less_release_off_the_button_is_deferred` | 1 | monkeypatch |
| `test_banking_does_not_double_count_the_running_clock` | 1 | monkeypatch |
| `test_the_countdown_is_paused_while_a_release_is_deferred` | 1 | monkeypatch |
| `test_a_press_inside_the_window_resumes_the_same_hold` | 1 | monkeypatch |
| `test_a_resumed_hold_keeps_its_progress_bar_position` | 1 | monkeypatch |
| `test_the_progress_bar_freezes_while_a_release_is_deferred` | 1 | monkeypatch |
| `test_a_tick_inside_the_deferral_repaints_without_advancing` | 1 | monkeypatch |
| `test_no_return_inside_the_window_is_a_real_release` | 1 | monkeypatch |
| `test_recovery_is_off_by_default` | 1 | monkeypatch |
| `test_a_completed_hold_is_not_deferred` | 1 | monkeypatch |
| `test_cancelling_clears_a_deferred_release` | 1 | monkeypatch |
| `test_an_enter_with_the_contact_still_down_resumes_the_hold` | 1 | monkeypatch |
| `test_an_enter_without_the_contact_does_not_resume` | 1 | monkeypatch |
| `test_motion_with_the_contact_down_also_resumes` | 1 | monkeypatch |
| `test_motion_is_ignored_when_no_release_is_deferred` | 1 | caplog |
| `test_an_unreadable_state_mask_does_not_resume` | 1 |  |
| `test_a_quick_restart_inherits_the_abandoned_progress` | 1 | caplog, monkeypatch |
| `test_an_unrelated_later_press_is_not_flagged_as_a_restart` | 1 | caplog, monkeypatch |
| `test_a_hold_that_fired_is_not_counted_as_abandoned` | 1 | monkeypatch |
| `test_a_slower_restart_is_flagged_but_starts_over` | 1 | caplog, monkeypatch |
| `test_the_unwrap_reads_state_through_guizeros_wrapper` | 1 |  |
| `test_the_hold_story_is_still_traced_with_verbose_tracing_off` | 1 | caplog, monkeypatch |
| `test_per_event_chatter_is_silent_until_verbose_tracing_is_enabled` | 1 | caplog, monkeypatch |
| `test_a_costly_detail_is_not_built_when_tracing_is_off` | 1 | monkeypatch |
| `test_verbose_tracing_ships_disabled` | 1 |  |
| `test_a_plain_button_does_not_carry_progress_between_presses` | 1 | caplog, monkeypatch |
| `test_a_callback_may_be_a_bare_function` | 1 |  |
| `test_a_callback_may_carry_positional_args` | 1 |  |
| `test_a_callback_may_carry_args_and_kwargs` | 1 |  |
| `test_an_absent_or_empty_callback_is_a_no_op` | 1 |  |
| `test_a_button_has_no_border_until_a_thickness_is_asked_for` | 1 |  |
| `test_asking_for_a_thickness_paints_the_border_in_the_color_already_worn` | 1 |  |
| `test_a_border_falls_back_to_the_face_tk_reports` | 1 |  |
| `test_setting_the_face_color_repaints_the_border_to_match` | 1 |  |
| `test_deselecting_returns_the_border_to_the_unselected_color` | 1 |  |
| `test_dropping_the_thickness_takes_the_border_away_for_good` | 1 |  |
| `test_a_thickness_below_zero_is_no_border_rather_than_an_error` | 1 |  |
| `test_the_border_is_left_alone_when_there_is_no_color_to_paint_it` | 1 |  |
| `test_a_torn_down_window_does_not_take_the_border_setter_down_with_it` | 1 |  |
| `test_macos_is_reported_as_not_painting_a_button_face` | 1 |  |
| `test_every_other_windowing_system_paints_a_button_face` | 2 | windowing_system |
| `test_a_face_is_assumed_painted_when_the_question_cannot_be_asked` | 1 |  |

## tests/gui/test_image_presenter.py

7 cases; 7 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_clear_caches_clears_image_and_path_indexes` | 1 |  |
| `test_update_ignores_stale_engine_callback_for_other_scope` | 1 | monkeypatch |
| `test_update_uses_cached_engine_image_without_recalculating_layout` | 1 | monkeypatch |
| `test_update_accepts_relevant_engine_callback_for_active_train` | 1 | monkeypatch |
| `test_update_schedules_custom_image_lookup_without_product_lookup` | 1 | monkeypatch |
| `test_custom_image_miss_marks_checked_and_queues_update` | 1 | monkeypatch |
| `test_custom_image_hit_caches_photo_image_and_queues_train_update` | 1 | monkeypatch |

## tests/gui/test_keypad_view.py

124 cases; 86 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_roster_key_spans_the_final_entry_row_at_standard_button_height` | 2 | _patch_widgets, button_size, monkeypatch |
| `test_roster_key_opens_the_catalog_for_the_current_scope` | 1 | _patch_widgets, monkeypatch |
| `test_roster_row_is_entry_only_and_releases_its_height_in_ops` | 5 | _patch_widgets, monkeypatch, scope |
| `test_accessory_throttle_repeats_until_release` | 1 | _patch_widgets, monkeypatch |
| `test_accessory_panel_kind_reports_each_panel` | 1 | _patch_widgets, monkeypatch |
| `test_accessory_panel_kind_prefers_the_more_specific_panel` | 1 | _patch_widgets, monkeypatch |
| `test_accessory_panel_kind_is_generic_for_an_lcs_component` | 1 | _patch_widgets, monkeypatch |
| `test_accessory_panel_kind_is_none_off_an_accessory_panel` | 1 | _patch_widgets, monkeypatch |
| `test_accessory_panel_kind_reports_bpc2_for_a_train_scope_power_district` | 1 | _patch_widgets, monkeypatch |
| `test_accessory_panel_kind_unwraps_a_configured_accessory_adapter` | 1 | _patch_widgets, monkeypatch |
| `test_asc2_control_sends_the_same_request_the_key_did` | 1 | _patch_widgets, monkeypatch |
| `test_the_on_screen_key_still_sends_through_the_enabled_widget` | 1 | _patch_widgets, monkeypatch |
| `test_asc2_control_sends_nothing_for_a_port_that_is_not_an_asc2` | 1 | _patch_widgets, monkeypatch |
| `test_the_sequence_send_is_widget_free_and_takes_the_pair_it_is_given` | 1 | _patch_widgets, monkeypatch |
| `test_the_change_handler_still_sends_what_the_group_shows` | 1 | _patch_widgets, monkeypatch |
| `test_stepping_moves_one_option_and_reports_where_it_landed` | 5 | _patch_widgets, delta, expected, monkeypatch, start |
| `test_stepping_off_either_end_moves_nothing` | 2 | _patch_widgets, delta, monkeypatch, start |
| `test_an_unset_selection_is_treated_as_the_first_option` | 2 | _patch_widgets, delta, monkeypatch |
| `test_a_selection_the_list_does_not_hold_is_read_as_unset` | 4 | _patch_widgets, monkeypatch, value |
| `test_the_highlighted_option_is_read_back_through_one_normalising` | 6 | _patch_widgets, expected, monkeypatch, value |
| `test_the_highlight_can_be_moved_to_a_named_option_without_sending` | 1 | _patch_widgets, monkeypatch |
| `test_the_highlight_is_not_moved_to_an_option_the_list_does_not_hold` | 4 | _patch_widgets, monkeypatch, value |
| `test_the_highlight_is_not_moved_where_the_panel_is_not_a_sensor_track` | 1 | _patch_widgets, monkeypatch |
| `test_the_cursor_falls_back_to_the_option_the_track_is_programmed_with` | 1 | _patch_widgets, monkeypatch |
| `test_the_cursor_can_be_cleared` | 1 | _patch_widgets, monkeypatch |
| `test_the_cursor_is_not_moved_to_an_option_the_list_does_not_hold` | 3 | _patch_widgets, monkeypatch, value |
| `test_stepping_the_whole_list_leaves_the_dot_where_it_was_and_sends_nothing` | 1 | _patch_widgets, monkeypatch |
| `test_a_tap_on_screen_brings_the_cursor_with_it` | 1 | _patch_widgets, monkeypatch |
| `test_stepping_is_refused_where_the_panel_is_not_a_sensor_track` | 1 | _patch_widgets, monkeypatch |
| `test_external_accessory_throttle_update_repaints_slider` | 1 | _patch_widgets, monkeypatch |
| `test_the_switch_and_route_keys_are_given_a_border_to_carry_their_color` | 1 | _patch_widgets, monkeypatch |
| `test_no_other_keypad_key_wears_a_border` | 1 | _patch_widgets, monkeypatch |
| `test_the_new_keys_take_the_free_slots_in_the_fourth_column` | 1 | _patch_widgets, monkeypatch |
| `test_the_generic_accessory_screen_carries_an_info_key` | 1 | _patch_widgets, monkeypatch |
| `test_the_switch_screen_carries_both_a_set_and_an_info_key` | 1 | _patch_widgets, monkeypatch |
| `test_neither_key_appears_on_a_route_screen` | 1 | _patch_widgets, monkeypatch |
| `test_route_builder_and_info_appear_on_route_ops` | 1 | _patch_widgets, monkeypatch |
| `test_route_entry_collapses_the_bottom_row_and_ops_restores_it` | 4 | _patch_widgets, clear_info, from_ops, monkeypatch |
| `test_leaving_route_entry_restores_the_bottom_row_for_other_scopes` | 4 | _patch_widgets, monkeypatch, scope |
| `test_route_builder_is_shared_with_entry_and_hidden_for_other_scopes` | 2 | _patch_widgets, clear_info, monkeypatch |
| `test_info_position_is_restored_when_leaving_route_ops` | 2 | _patch_widgets, monkeypatch, scope |
| `test_the_info_key_stays_off_the_lcs_specific_panels` | 4 | _patch_widgets, flag, monkeypatch |
| `test_entry_mode_hides_both_new_keys` | 1 | _patch_widgets, monkeypatch |
| `test_the_info_key_opens_the_state_info_panel` | 1 | _patch_widgets, monkeypatch |
| `test_the_switch_set_key_fires_set_address_for_the_displayed_switch` | 1 | _patch_widgets, monkeypatch |
| `test_the_lcs_keypad_panels_carry_the_key_to_the_generic_panel` | 2 | _patch_widgets, flag, monkeypatch |
| `test_the_native_asc2_panel_carries_the_set_key_and_the_shared_lcs_key` | 1 | _patch_widgets, monkeypatch |
| `test_the_native_bpc2_panel_carries_the_shared_lcs_key_in_the_first_column` | 1 | _patch_widgets, monkeypatch |
| `test_the_lcs_key_is_a_single_shared_widget_re_gridded_across_the_native_panels` | 1 | _patch_widgets, monkeypatch |
| `test_the_switch_screen_carries_the_shared_lcs_key_below_its_set_key` | 1 | _patch_widgets, monkeypatch |
| `test_the_route_screen_carries_no_lcs_key` | 1 | _patch_widgets, monkeypatch |
| `test_the_shared_lcs_key_rides_the_entry_keypad_for_accessory_and_switch_scopes` | 1 | _patch_widgets, monkeypatch |
| `test_the_shared_lcs_key_stays_off_the_entry_keypad_for_other_scopes` | 3 | _patch_widgets, monkeypatch, scope |
| `test_the_generic_accessory_screen_carries_the_shared_lcs_key_under_zero` | 1 | _patch_widgets, monkeypatch |
| `test_the_generic_screen_yields_the_slot_to_the_way_back_key_when_configured` | 1 | _patch_widgets, monkeypatch |
| `test_a_configured_accessory_with_no_adapter_left_leaves_the_screen_alone` | 1 | _patch_widgets, monkeypatch |
| `test_the_shared_lcs_key_is_hidden_when_it_returns_to_entry_mode_from_an_ops_panel` | 1 | _patch_widgets, monkeypatch |
| `test_the_asc2_set_key_fires_acc_set_address` | 1 | _patch_widgets, monkeypatch |
| `test_the_lcs_panel_key_opens_the_hosts_lcs_configuration_panel` | 1 | _patch_widgets, monkeypatch |
| `test_the_generic_and_switch_panels_do_not_carry_it` | 1 | _patch_widgets, monkeypatch |
| `test_the_sensor_track_panel_no_longer_builds_a_generic_toggle` | 1 | _patch_widgets, monkeypatch |
| `test_the_override_decides_the_panel_drawn_and_the_kind_reported` | 1 | _patch_widgets, monkeypatch |
| `test_the_forced_generic_panel_offers_the_way_back_on_the_shared_key` | 1 | _patch_widgets, monkeypatch |
| `test_the_way_back_wears_the_configured_accessorys_own_op_icon` | 1 | _patch_widgets, monkeypatch |
| `test_the_way_back_falls_back_to_the_device_icon_when_the_accessory_defines_no_op_icon` | 1 | _patch_widgets, monkeypatch |
| `test_without_an_override_the_shared_key_still_opens_the_configured_overlay` | 1 | _patch_widgets, monkeypatch |
| `test_the_operating_accessory_key_wears_the_accessorys_own_op_icon` | 1 | _patch_widgets, monkeypatch |
| `test_the_operating_accessory_key_falls_back_to_op_screen_when_no_icon_is_defined` | 1 | _patch_widgets, monkeypatch |
| `test_the_operating_accessory_key_falls_back_when_the_attribute_is_absent` | 1 | _patch_widgets, monkeypatch |
| `test_a_generic_component_forced_generic_has_no_other_view_to_offer` | 1 | _patch_widgets, monkeypatch |
| `test_the_override_does_not_survive_a_return_to_entry_mode` | 1 | _patch_widgets, monkeypatch |
| `test_reflow_collapses_columns_with_no_visible_cell` | 1 | _patch_widgets, monkeypatch |
| `test_reflow_restores_a_column_once_one_of_its_cells_is_visible` | 1 | _patch_widgets, monkeypatch |
| `test_reflow_counts_an_aux_cell_relocated_to_the_fourth_column` | 1 | _patch_widgets, monkeypatch |
| `test_reflow_keeps_the_numeric_columns_even_with_a_hidden_cell_among_them` | 1 | _patch_widgets, monkeypatch |
| `test_reflow_tightens_the_pad_to_the_occupied_column_count` | 1 | _patch_widgets, monkeypatch |
| `test_reflow_widens_the_pad_when_the_fourth_column_fills` | 1 | _patch_widgets, monkeypatch |
| `test_build_files_every_keypad_cell_including_the_throttle_into_the_roster` | 1 | _patch_widgets, monkeypatch |
| `test_reflow_after_build_collapses_the_empty_fourth_and_fifth_columns` | 1 | _patch_widgets, monkeypatch |
| `test_entry_mode_collapses_the_fourth_and_fifth_columns` | 1 | _patch_widgets, monkeypatch |
| `test_route_ops_leaves_the_fourth_column_collapsed` | 1 | _patch_widgets, monkeypatch |
| `test_switch_ops_expands_the_fourth_column` | 1 | _patch_widgets, monkeypatch |
| `test_generic_accessory_ops_expands_the_fourth_and_fifth_columns` | 1 | _patch_widgets, monkeypatch |
| `test_the_bpc2_panel_collapses_the_fourth_column` | 1 | _patch_widgets, monkeypatch |
| `test_the_asc2_panel_expands_the_fourth_column_for_its_set_and_lcs_keys` | 1 | _patch_widgets, monkeypatch |
| `test_returning_to_entry_after_ops_recollapses_the_fourth_column` | 1 | _patch_widgets, monkeypatch |

## tests/gui/test_lcs_config_panel.py

424 cases; 375 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_build_shows_device_page_first` | 1 | _patch_widgets, monkeypatch |
| `test_next_page_requires_a_device_then_shows_id_page` | 1 | _patch_widgets, monkeypatch |
| `test_device_options_cover_every_registry_device` | 1 | _patch_widgets, monkeypatch |
| `test_device_options_are_sorted_by_name` | 1 | _patch_widgets, monkeypatch |
| `test_set_base_id_clamps_at_one` | 1 | _patch_widgets, monkeypatch |
| `test_set_base_id_clamps_at_mode_max` | 1 | _patch_widgets, monkeypatch |
| `test_step_keys_disable_exactly_at_the_limits` | 1 | _patch_widgets, monkeypatch |
| `test_keypad_commit_of_bad_text_leaves_the_id_alone` | 1 | _patch_widgets, monkeypatch |
| `test_the_mode_rows_name_the_block_each_of_them_would_claim` | 1 | _patch_widgets, monkeypatch |
| `test_stepping_the_id_relabels_every_mode_row` | 1 | _patch_widgets, monkeypatch |
| `test_a_mode_row_is_offered_at_the_highest_base_it_fits` | 1 | _patch_widgets, monkeypatch |
| `test_the_page_says_the_selected_block_once` | 1 | _patch_widgets, monkeypatch |
| `test_widening_the_mode_lowers_an_out_of_range_id` | 1 | _patch_widgets, monkeypatch |
| `test_configure_with_nothing_selected_defaults_to_id_one_and_the_first_device` | 1 | _patch_widgets, monkeypatch |
| `test_the_default_device_is_the_first_one_offered` | 1 | _patch_widgets, monkeypatch |
| `test_the_first_page_is_never_a_dead_end` | 1 | _patch_widgets, monkeypatch |
| `test_a_desktop_opens_on_the_first_device_whatever_holds_the_id` | 1 | _patch_widgets, monkeypatch |
| `test_an_appliance_falls_back_to_the_first_device_when_the_id_is_free` | 1 | _patch_widgets, monkeypatch |
| `test_the_entered_id_is_squared_with_the_opening_modes_ceiling` | 1 | _patch_widgets, monkeypatch |
| `test_configure_seeds_device_and_mode_from_a_known_bpc2_state` | 1 | _patch_widgets, monkeypatch |
| `test_configure_seeds_from_the_store_when_the_id_is_a_known_base` | 1 | _patch_widgets, monkeypatch |
| `test_unowned_id_reports_unassigned` | 1 | _patch_widgets, monkeypatch |
| `test_interior_port_reports_its_owner_and_offers_both_choices` | 1 | _patch_widgets, monkeypatch |
| `test_the_two_choices_are_drawn_as_the_panels_other_keys_are` | 1 | _patch_widgets, monkeypatch |
| `test_the_two_choices_are_read_at_a_size_worth_pressing` | 1 | _patch_widgets, monkeypatch |
| `test_white_space_stands_between_the_two_choices` | 1 | _patch_widgets, monkeypatch |
| `test_the_white_space_between_the_two_choices_survives_them_being_shown` | 1 | _patch_widgets, monkeypatch |
| `test_go_to_base_retargets_and_pre_fills` | 1 | _patch_widgets, monkeypatch |
| `test_go_to_base_ignores_a_module_on_another_remote_key` | 1 | _patch_widgets, monkeypatch |
| `test_configure_as_new_keeps_the_entered_id` | 1 | _patch_widgets, monkeypatch |
| `test_overlaps_are_advisory` | 1 | _patch_widgets, monkeypatch |
| `test_the_module_answering_to_the_entered_id_is_not_named_as_an_overlap_too` | 1 | _patch_widgets, monkeypatch |
| `test_a_switch_mode_asc2_overlaps_a_switch_module_that_runs_into_it` | 1 | _patch_widgets, monkeypatch |
| `test_an_accessory_never_overlaps_a_switch_block` | 1 | _patch_widgets, monkeypatch |
| `test_the_assigned_box_names_the_module_on_the_key_being_programmed` | 1 | _patch_widgets, monkeypatch |
| `test_the_same_id_reports_a_different_module_for_a_different_key` | 1 | _patch_widgets, monkeypatch |
| `test_switching_an_asc2_between_keys_changes_what_is_in_its_way` | 1 | _patch_widgets, monkeypatch |
| `test_with_no_device_chosen_every_module_still_counts` | 1 | _patch_widgets, monkeypatch |
| `test_configure_prefers_a_module_on_the_screens_own_key` | 1 | _patch_widgets, monkeypatch |
| `test_configure_widens_the_search_when_the_screen_is_not_on_an_lcs_key` | 1 | _patch_widgets, monkeypatch |
| `test_sensor_track_claims_a_single_id` | 1 | _patch_widgets, monkeypatch |
| `test_a_train_holds_a_track_address_against_the_module_being_programmed` | 1 | _patch_widgets, monkeypatch |
| `test_a_train_is_named_for_its_road_and_for_what_it_is_otherwise` | 1 | _patch_widgets, monkeypatch |
| `test_a_train_row_is_colored_as_the_warning_it_is` | 1 | _patch_widgets, monkeypatch |
| `test_the_trains_are_nothing_to_a_module_on_the_accessory_keys` | 1 | _patch_widgets, monkeypatch |
| `test_switching_a_bpc2_between_its_two_keys_changes_whether_the_trains_are_in_the_way` | 1 | _patch_widgets, monkeypatch |
| `test_only_a_track_mode_shares_the_trains_addresses` | 1 | _patch_widgets, monkeypatch |
| `test_before_a_mode_is_chosen_no_block_is_taken_from_anyone` | 1 | _patch_widgets, monkeypatch |
| `test_a_train_is_no_module_to_go_to_or_to_read_settings_off` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_addressed_as_a_track_device_is_not_reported_as_a_train_too` | 1 | _patch_widgets, monkeypatch |
| `test_the_modules_are_named_before_the_trains` | 1 | _patch_widgets, monkeypatch |
| `test_options_page_renders_only_the_selected_device_controls` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_with_no_options_gets_no_controls_and_no_page` | 1 | _patch_widgets, monkeypatch |
| `test_the_amc2_offers_a_mode_and_a_remember_flag_for_each_of_its_two_motors` | 1 | _patch_widgets, monkeypatch |
| `test_the_amc2_motor_modes_are_the_three_the_manual_describes` | 1 | _patch_widgets, monkeypatch |
| `test_choosing_a_motor_mode_writes_that_motors_press_alone` | 1 | _patch_widgets, monkeypatch |
| `test_a_setting_below_the_one_being_marked_keeps_the_pad_on_the_page` | 1 | _patch_widgets, monkeypatch |
| `test_the_options_page_names_the_module_and_the_addresses_it_will_answer_to` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_holding_a_single_address_names_that_address_alone` | 1 | _patch_widgets, monkeypatch |
| `test_the_options_page_holds_nothing_between_the_heading_and_the_settings` | 1 | _patch_widgets, monkeypatch |
| `test_toggling_the_bpc2_restore_flag_updates_the_presses` | 1 | _patch_widgets, monkeypatch |
| `test_sensor_track_action_is_required_and_defaults_to_no_action` | 1 | _patch_widgets, monkeypatch |
| `test_sensor_track_action_is_seeded_from_the_irda_state` | 1 | _patch_widgets, monkeypatch |
| `test_choosing_an_action_command_changes_the_press_digit` | 1 | _patch_widgets, monkeypatch |
| `test_the_lone_checkbox_is_painted_like_the_radio_lists` | 1 | _patch_widgets, monkeypatch |
| `test_the_checkbox_is_painted_at_the_size_the_mode_radios_use` | 1 | _patch_widgets, monkeypatch |
| `test_the_action_rows_are_set_at_the_size_every_other_control_is_and_one_length` | 1 | _patch_widgets, monkeypatch |
| `test_the_longest_list_is_set_at_the_size_the_lone_control_and_the_mode_rows_are` | 1 | _patch_widgets, monkeypatch |
| `test_the_action_rows_are_headed_by_the_one_word` | 1 | _patch_widgets, monkeypatch |
| `test_nothing_is_read_under_the_action_rows` | 1 | _patch_widgets, monkeypatch |
| `test_the_engine_id_filters_are_still_reported_in_the_read_back` | 1 | _patch_widgets, monkeypatch |
| `test_a_short_radio_list_is_set_at_the_size_a_lone_control_is` | 1 | _patch_widgets, monkeypatch |
| `test_the_whitespace_a_row_may_take_is_decided_by_the_whole_page` | 1 | _patch_widgets, monkeypatch |
| `test_a_note_on_a_full_page_gets_no_padding_either` | 1 | _patch_widgets, monkeypatch |
| `test_the_options_page_holds_its_rows_and_its_prose_apart` | 2 | _patch_widgets, compact, monkeypatch, note_pad, option_pad |
| `test_the_option_rows_are_held_apart_between_the_two_other_lists` | 1 | _patch_widgets, monkeypatch |
| `test_the_pages_prose_is_read_at_the_body_size_not_below_it` | 1 | _patch_widgets, monkeypatch |
| `test_every_line_of_prose_the_panel_draws_is_wrapped_to_the_popups_width` | 1 | _patch_widgets, monkeypatch |
| `test_a_checkbox_label_is_wrapped_from_the_left_beside_its_indicator` | 1 | _patch_widgets, monkeypatch |
| `test_an_options_own_note_is_wrapped_and_read_at_the_body_size` | 1 | _patch_widgets, monkeypatch |
| `test_the_wrap_is_the_width_the_popup_is_built_to` | 1 | _patch_widgets, monkeypatch |
| `test_the_wrap_falls_back_to_the_pane_and_then_to_a_floor` | 1 | _patch_widgets, monkeypatch |
| `test_a_page_is_drawn_in_the_pane_less_the_room_the_scroll_bar_takes` | 1 | _patch_widgets, monkeypatch |
| `test_a_line_with_nothing_to_say_leaves_the_page_and_takes_its_gaps_with_it` | 1 | _patch_widgets, monkeypatch |
| `test_the_heading_is_followed_by_the_module_then_a_gap_then_the_settings` | 1 | _patch_widgets, monkeypatch |
| `test_only_a_module_with_no_options_skips_the_page` | 4 | _patch_widgets, key, monkeypatch, skipped |
| `test_no_module_chosen_yet_skips_nothing` | 1 | _patch_widgets, monkeypatch |
| `test_next_goes_from_the_id_straight_to_the_review_for_a_module_with_no_options` | 1 | _patch_widgets, monkeypatch |
| `test_back_comes_straight_back_from_the_review_to_the_id` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_with_an_option_still_stops_on_the_page` | 1 | _patch_widgets, monkeypatch |
| `test_the_page_is_still_built_so_the_review_keeps_its_index` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_that_changes_under_the_open_page_falls_back_rather_than_forward` | 1 | _patch_widgets, monkeypatch |
| `test_stepping_past_the_last_page_still_lands_on_the_review` | 1 | _patch_widgets, monkeypatch |
| `test_review_page_is_numbered_in_send_order_with_the_pgm_instruction` | 1 | _patch_widgets, monkeypatch |
| `test_the_sensor_tracks_review_names_its_own_program_button` | 1 | _patch_widgets, monkeypatch |
| `test_the_relay_warning_is_read_on_the_page_it_is_acted_on` | 1 | _patch_widgets, monkeypatch |
| `test_the_review_pages_heading_is_followed_by_half_a_line_then_the_instruction` | 1 | _patch_widgets, monkeypatch |
| `test_the_instruction_and_the_steps_are_read_at_the_pages_own_size` | 1 | _patch_widgets, monkeypatch |
| `test_the_steps_stand_in_a_box_of_their_own_drawn_to_the_page` | 1 | _patch_widgets, monkeypatch |
| `test_the_steps_box_stands_in_a_margin_either_side_of_it` | 1 | _patch_widgets, monkeypatch |
| `test_the_steps_box_keeps_its_width_across_a_refresh` | 1 | _patch_widgets, monkeypatch |
| `test_the_steps_read_from_the_left_edge_of_their_box` | 1 | _patch_widgets, monkeypatch |
| `test_the_configure_key_stands_where_the_keys_below_it_stand` | 1 | _patch_widgets, monkeypatch |
| `test_the_space_beside_the_key_is_what_the_window_is_keeping_from_the_page` | 1 | _patch_widgets, monkeypatch |
| `test_a_fit_that_left_the_window_keeping_the_same_room_does_not_move_the_key` | 1 | _patch_widgets, monkeypatch |
| `test_white_space_stands_either_side_of_the_configure_key` | 1 | _patch_widgets, monkeypatch |
| `test_configure_queues_the_presses_in_order_then_the_verify_gets` | 1 | _patch_widgets, monkeypatch |
| `test_configure_of_a_sensor_track_always_sends_both_halves` | 1 | _patch_widgets, monkeypatch |
| `test_the_module_is_asked_again_and_again_while_the_panel_waits` | 1 | _patch_widgets, monkeypatch |
| `test_a_sequence_that_runs_past_the_wait_is_still_asked_once` | 1 | _patch_widgets, monkeypatch |
| `test_the_status_line_is_not_colored_as_an_answer_until_there_is_one` | 1 | _patch_widgets, monkeypatch |
| `test_the_configure_button_wears_the_shared_look_of_the_overlays_other_keys` | 1 | _patch_widgets, monkeypatch |
| `test_the_my_modules_key_is_drawn_as_a_key_like_the_ones_beside_it` | 1 | _patch_widgets, monkeypatch |
| `test_read_back_reports_what_the_module_says` | 1 | _patch_widgets, monkeypatch |
| `test_read_back_timeout_reports_no_response_and_leaves_the_presses` | 1 | _patch_widgets, monkeypatch |
| `test_reopening_the_panel_clears_the_previous_read_back` | 1 | _patch_widgets, monkeypatch |
| `test_mode_selector_repopulates_correctly_on_device_change` | 1 | _patch_widgets, monkeypatch |
| `test_panel_is_not_sync_pending_by_default` | 1 | _patch_widgets, monkeypatch |
| `test_sync_pending_shows_the_banner_and_disables_configure` | 1 | _patch_widgets, monkeypatch |
| `test_every_other_control_stays_usable_while_sync_is_pending` | 1 | _patch_widgets, monkeypatch |
| `test_occupancy_is_unassigned_until_the_store_is_populated` | 1 | _patch_widgets, monkeypatch |
| `test_on_synchronized_re_seeds_while_the_operator_has_not_chosen` | 1 | _patch_widgets, monkeypatch |
| `test_on_synchronized_keeps_the_operators_choices` | 1 | _patch_widgets, monkeypatch |
| `test_on_synchronized_is_idempotent` | 1 | _patch_widgets, monkeypatch |
| `test_both_radio_lists_are_stretched_to_the_box_around_them` | 1 | _patch_widgets, monkeypatch |
| `test_neither_radio_list_is_built_with_an_explicit_row_width` | 1 | _patch_widgets, monkeypatch |
| `test_the_titled_boxes_are_stacked_in_one_column` | 1 | _patch_widgets, monkeypatch |
| `test_every_showing_box_is_stretched_across_that_column_and_spaced_from_the_next` | 1 | _patch_widgets, monkeypatch |
| `test_the_gap_between_the_boxes_is_tighter_on_a_compact_host` | 2 | _patch_widgets, compact, gap, monkeypatch |
| `test_a_hidden_box_is_not_stretched_back_onto_the_screen` | 1 | _patch_widgets, monkeypatch |
| `test_the_stretch_is_re_applied_on_every_id_page_refresh` | 1 | _patch_widgets, monkeypatch |
| `test_the_boxes_are_drawn_no_narrower_than_the_page_they_stand_on` | 1 | _patch_widgets, monkeypatch |
| `test_a_host_that_has_measured_nothing_still_gets_boxes_wider_than_the_wrap` | 1 | _patch_widgets, monkeypatch |
| `test_equalizing_survives_a_tcl_error` | 1 | _patch_widgets, monkeypatch |
| `test_every_spacer_that_is_asked_for_and_no_other` | 1 | _patch_widgets, monkeypatch |
| `test_the_body_spacer_comes_before_the_sync_line_and_the_pages` | 1 | _patch_widgets, monkeypatch |
| `test_the_device_page_spacer_sits_between_the_prompt_and_the_group` | 1 | _patch_widgets, monkeypatch |
| `test_the_id_pages_sections_are_held_apart` | 1 | _patch_widgets, monkeypatch |
| `test_the_gaps_are_tighter_on_a_compact_host` | 2 | _patch_widgets, compact, heading, id_page, monkeypatch, page, prose, section |
| `test_the_row_of_keys_is_the_last_thing_in_the_body_after_a_gap` | 1 | _patch_widgets, monkeypatch |
| `test_the_first_page_holds_the_row_of_keys_off_at_either_end` | 3 | _patch_widgets, compact, key, monkeypatch |
| `test_the_band_is_a_keys_own_height_up_to_what_the_tightest_screen_can_spare` | 5 | _patch_widgets, expected, key, monkeypatch |
| `test_the_row_of_keys_is_left_a_keys_worth_of_room_at_either_end` | 3 | _patch_widgets, compact, key, monkeypatch |
| `test_no_page_but_the_first_is_given_the_band` | 1 | _patch_widgets, monkeypatch |
| `test_the_band_is_set_before_the_window_is_given_the_room_that_is_left` | 1 | _patch_widgets, monkeypatch |
| `test_the_gaps_are_not_re_sized_for_a_band_that_did_not_change` | 1 | _patch_widgets, monkeypatch |
| `test_a_gap_that_will_not_take_the_band_costs_the_page_turn_nothing` | 1 | _patch_widgets, monkeypatch |
| `test_a_key_no_screen_can_measure_leaves_the_band_at_the_cap` | 1 | _patch_widgets, monkeypatch |
| `test_the_panel_offers_no_footer_so_close_gets_a_line_of_its_own` | 1 | _patch_widgets, monkeypatch |
| `test_the_platform_alone_decides_close_only_where_the_panel_is_the_window` | 2 | _patch_widgets, linux, monkeypatch |
| `test_a_panel_inside_a_pane_carries_close_whatever_the_platform` | 2 | _patch_widgets, linux, monkeypatch |
| `test_declining_close_is_this_panel_and_no_other` | 1 | _patch_widgets, monkeypatch |
| `test_the_panel_holds_the_screen_where_it_carries_its_own_way_off_it` | 4 | _patch_widgets, linux, monkeypatch, owns_window |
| `test_holding_the_screen_is_this_panel_and_no_other` | 1 | _patch_widgets, monkeypatch |
| `test_the_device_page_shows_my_modules_and_next` | 1 | _patch_widgets, monkeypatch |
| `test_back_is_visible_and_enabled_on_every_later_page` | 1 | _patch_widgets, monkeypatch |
| `test_the_keys_are_created_in_the_order_they_are_read` | 1 | _patch_widgets, monkeypatch |
| `test_stepping_forward_and_back_restores_the_initial_visibility` | 1 | _patch_widgets, monkeypatch |
| `test_the_rows_packing_is_replayed_after_every_toggle` | 1 | _patch_widgets, monkeypatch |
| `test_next_enablement_is_unchanged_by_the_hidden_back_button` | 1 | _patch_widgets, monkeypatch |
| `test_next_leaves_the_row_on_the_page_it_could_never_lead_off` | 1 | _patch_widgets, monkeypatch |
| `test_next_stands_grayed_where_there_is_a_page_but_nothing_to_go_on_with` | 1 | _patch_widgets, monkeypatch |
| `test_the_nav_row_gives_back_the_footer_bands_vertical_padding` | 2 | _patch_widgets, compact, expected, monkeypatch |
| `test_the_band_below_the_row_is_the_rows_own_whitespace` | 2 | _patch_widgets, compact, expected, monkeypatch |
| `test_the_row_holds_its_keys_and_nothing_else` | 1 | _patch_widgets, monkeypatch |
| `test_the_id_heading_names_the_selected_module` | 1 | _patch_widgets, monkeypatch |
| `test_the_editors_own_header_is_named_with_the_heading` | 1 | _patch_widgets, monkeypatch |
| `test_the_id_editor_follows_the_platform` | 2 | _patch_widgets, editor, monkeypatch, on_screen, touch |
| `test_the_id_box_opens_for_typing_on_a_press` | 2 | _patch_widgets, linux, monkeypatch |
| `test_the_press_leaves_the_components_own_hold_alone` | 2 | _patch_widgets, linux, monkeypatch |
| `test_touch_only_editing_asks_the_platform_helper` | 2 | _patch_widgets, linux, monkeypatch |
| `test_the_mode_radios_are_in_a_box_titled_mode` | 1 | _patch_widgets, monkeypatch |
| `test_the_mode_box_is_hidden_until_a_device_declares_modes` | 1 | _patch_widgets, monkeypatch |
| `test_the_mode_options_are_larger_than_the_page_body` | 1 | _patch_widgets, monkeypatch |
| `test_both_radio_lists_hold_their_rows_apart` | 2 | _patch_widgets, compact, device, mode, monkeypatch |
| `test_the_mode_rows_are_held_apart_less_than_the_module_rows` | 1 | _patch_widgets, monkeypatch |
| `test_the_three_titled_boxes_are_labelled_at_the_page_body_size` | 1 | _patch_widgets, monkeypatch |
| `test_the_module_rows_are_body_size_and_the_mode_boxs_prose_below_it` | 1 | _patch_widgets, monkeypatch |
| `test_the_mode_sits_directly_under_the_id_row_and_the_reports_below_both` | 1 | _patch_widgets, monkeypatch |
| `test_the_assignment_line_is_in_a_box_titled_currently_assigned` | 1 | _patch_widgets, monkeypatch |
| `test_an_unassigned_id_says_so_rather_than_going_blank` | 1 | _patch_widgets, monkeypatch |
| `test_an_assigned_id_names_the_module_its_remote_key_and_its_block` | 4 | _patch_widgets, device_key, expected, flag, mode, monkeypatch, num_ids, scope |
| `test_the_row_is_gridded_with_the_remote_key_first_and_bold` | 1 | _patch_widgets, monkeypatch |
| `test_an_interior_hit_does_not_spell_out_which_port_it_is` | 1 | _patch_widgets, monkeypatch |
| `test_the_overlaps_are_in_a_box_of_their_own_titled_overlaps` | 1 | _patch_widgets, monkeypatch |
| `test_each_module_in_the_way_gets_a_row_of_its_own` | 1 | _patch_widgets, monkeypatch |
| `test_the_overlaps_box_comes_and_goes_with_what_is_in_the_way` | 1 | _patch_widgets, monkeypatch |
| `test_the_assigned_box_names_every_module_the_pdi_bus_reported` | 1 | _patch_widgets, monkeypatch |
| `test_the_shared_record_alone_could_not_say_that` | 1 | _patch_widgets, monkeypatch |
| `test_an_id_inside_the_true_block_is_reported_against_that_block` | 1 | _patch_widgets, monkeypatch |
| `test_every_module_on_the_id_gets_a_row_of_its_own` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_this_pass_cannot_program_is_named_but_never_seeded_from` | 1 | _patch_widgets, monkeypatch |
| `test_opening_the_panel_from_an_amc2_screen_opens_it_on_the_amc2` | 1 | _patch_widgets, monkeypatch |
| `test_the_amc2_is_offered_on_the_accessory_key_alone` | 1 | _patch_widgets, monkeypatch |
| `test_an_amc2_addressed_as_a_train_is_not_opened_on_a_mode_the_panel_cannot_offer` | 1 | _patch_widgets, monkeypatch |
| `test_the_choice_buttons_ignore_a_module_that_cannot_be_programmed` | 1 | _patch_widgets, monkeypatch |
| `test_a_row_left_over_from_a_busier_id_is_hidden_not_blanked` | 1 | _patch_widgets, monkeypatch |
| `test_the_mode_radios_open_on_the_mode_the_module_is_running_in` | 1 | _patch_widgets, monkeypatch |
| `test_the_settings_are_read_off_the_module_on_the_key_it_reported` | 1 | _patch_widgets, monkeypatch |
| `test_the_mode_the_operator_picks_is_not_read_over` | 1 | _patch_widgets, monkeypatch |
| `test_choosing_another_module_reads_the_layout_afresh` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_of_another_type_at_the_address_leaves_the_radios_alone` | 1 | _patch_widgets, monkeypatch |
| `test_an_id_inside_the_block_is_not_the_module_and_leaves_the_radios_alone` | 1 | _patch_widgets, monkeypatch |
| `test_a_mode_read_off_a_module_stays_put_at_an_address_nothing_answers_to` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_running_in_a_mode_the_manual_reserves_leaves_the_radios_alone` | 1 | _patch_widgets, monkeypatch |
| `test_the_mode_is_read_again_once_the_base_has_reported` | 1 | _patch_widgets, monkeypatch |
| `test_the_restore_box_shows_what_the_bpc2_at_the_address_is_holding` | 2 | _patch_widgets, monkeypatch, restore |
| `test_only_the_module_at_the_address_is_read_and_only_on_the_key_being_programmed` | 1 | _patch_widgets, monkeypatch |
| `test_a_setting_read_off_one_module_is_not_carried_to_an_empty_address` | 1 | _patch_widgets, monkeypatch |
| `test_what_the_operator_sets_is_not_read_over_while_the_panel_stays_on_the_address` | 1 | _patch_widgets, monkeypatch |
| `test_the_module_is_read_again_once_the_base_has_reported` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_of_another_type_at_the_address_is_not_read_for_its_settings` | 1 | _patch_widgets, monkeypatch |
| `test_the_motor_rows_show_what_the_amc2_at_the_address_is_running` | 1 | _patch_widgets, monkeypatch |
| `test_an_amc2_that_has_reported_no_motors_leaves_them_at_their_defaults` | 1 | _patch_widgets, monkeypatch |
| `test_the_read_back_names_each_motor_and_whether_it_remembers` | 1 | _patch_widgets, monkeypatch |
| `test_the_action_command_shows_what_the_sensor_track_at_the_address_is_set_to` | 2 | _patch_widgets, monkeypatch, sequence |
| `test_the_config_record_is_what_the_action_command_is_read_from` | 1 | _patch_widgets, monkeypatch |
| `test_an_option_is_read_on_the_field_the_module_reports_it_on` | 1 | _patch_widgets, monkeypatch |
| `test_a_field_that_means_something_else_on_the_record_is_not_taken_as_an_answer` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_reporting_what_it_was_sent_is_a_success` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_holding_something_else_is_unsuccessful_and_says_what` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_reporting_another_mode_is_unsuccessful` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_that_never_answers_is_unsuccessful_too` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_that_answers_after_the_panel_gave_up_is_still_heard` | 1 | _patch_widgets, monkeypatch |
| `test_the_reminder_names_the_button_the_module_really_has` | 5 | _patch_widgets, device, monkeypatch |
| `test_a_setting_the_module_says_nothing_about_is_not_faulted` | 1 | _patch_widgets, monkeypatch |
| `test_a_motor_holding_another_mode_is_named_by_the_motor` | 1 | _patch_widgets, monkeypatch |
| `test_two_settings_a_module_names_alike_are_told_apart_by_their_motor` | 1 | _patch_widgets, monkeypatch |
| `test_a_setting_a_module_names_only_once_is_named_by_that_alone` | 1 | _patch_widgets, monkeypatch |
| `test_the_verdict_is_given_on_what_was_sent_and_not_on_what_the_pages_now_show` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_of_another_type_at_the_address_does_not_answer_for_it` | 1 | _patch_widgets, monkeypatch |
| `test_nothing_is_judged_before_anything_is_sent` | 1 | _patch_widgets, monkeypatch |
| `test_the_verdict_is_cleared_when_the_panel_is_reopened` | 1 | _patch_widgets, monkeypatch |
| `test_the_verdict_is_brought_into_view_when_it_is_written` | 1 | _patch_widgets, monkeypatch |
| `test_a_line_taken_off_the_page_is_not_scrolled_to` | 1 | _patch_widgets, monkeypatch |
| `test_the_verdict_stands_below_the_two_lines_it_is_drawn_from` | 1 | _patch_widgets, monkeypatch |
| `test_the_verdict_is_the_largest_text_on_the_page` | 1 | _patch_widgets, monkeypatch |
| `test_the_polling_line_is_read_as_the_note_it_is` | 1 | _patch_widgets, monkeypatch |
| `test_the_verdict_takes_the_line_back_from_the_poll` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_already_at_the_id_is_reported_in_dark_red` | 1 | _patch_widgets, monkeypatch |
| `test_an_address_nobody_holds_is_reported_in_dark_green` | 1 | _patch_widgets, monkeypatch |
| `test_every_module_in_the_way_is_reported_in_dark_red` | 1 | _patch_widgets, monkeypatch |
| `test_the_very_same_cells_turn_green_when_the_address_frees_up` | 1 | _patch_widgets, monkeypatch |
| `test_the_two_report_colors_are_dark_shades` | 1 | _patch_widgets, monkeypatch |
| `test_the_legend_heads_the_mode_box_and_the_note_ends_it` | 1 | _patch_widgets, monkeypatch |
| `test_both_lines_of_prose_are_centered_and_wrapped` | 1 | _patch_widgets, monkeypatch |
| `test_the_radios_are_held_off_the_prose_on_either_side_of_them` | 1 | _patch_widgets, monkeypatch |
| `test_no_device_means_neither_line_says_anything` | 1 | _patch_widgets, monkeypatch |
| `test_the_legend_covers_every_key_the_module_offers_and_no_other` | 4 | _patch_widgets, device_key, expected, monkeypatch |
| `test_the_legend_says_what_each_key_is_for` | 1 | _patch_widgets, monkeypatch |
| `test_a_key_that_means_the_same_everywhere_is_worded_once` | 1 | _patch_widgets, monkeypatch |
| `test_a_line_written_for_one_module_names_that_module` | 1 | _patch_widgets, monkeypatch |
| `test_the_bpc2s_two_keys_are_two_ways_of_addressing_it_rather_than_two_uses` | 1 | _patch_widgets, monkeypatch |
| `test_no_legend_line_asks_for_more_than_one_line_of_the_pane` | 1 | _patch_widgets, monkeypatch |
| `test_the_legend_leads_with_the_word_the_rows_lead_with` | 1 | _patch_widgets, monkeypatch |
| `test_the_legend_speaks_for_the_module_rather_than_for_the_chosen_row` | 1 | _patch_widgets, monkeypatch |
| `test_the_selected_mode_says_what_it_is_for_below_the_rows` | 1 | _patch_widgets, monkeypatch |
| `test_the_note_speaks_for_the_row_the_operator_chose` | 1 | _patch_widgets, monkeypatch |
| `test_a_mode_named_by_its_key_alone_keys_nothing` | 1 | _patch_widgets, monkeypatch |
| `test_a_mode_with_nothing_written_about_it_adds_no_line` | 1 | _patch_widgets, monkeypatch |
| `test_the_legend_follows_the_device_the_operator_switches_to` | 1 | _patch_widgets, monkeypatch |
| `test_the_rows_of_one_key_are_held_off_the_rows_of_the_next` | 1 | _patch_widgets, monkeypatch |
| `test_the_gap_falls_wherever_the_key_changes` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_whose_modes_share_one_key_asks_for_no_gap` | 2 | _patch_widgets, device_key, monkeypatch |
| `test_no_device_means_no_gaps` | 1 | _patch_widgets, monkeypatch |
| `test_the_group_is_told_the_gaps_when_it_is_built_and_on_every_refresh` | 1 | _patch_widgets, monkeypatch |
| `test_the_gap_between_keys_is_tighter_on_a_compact_host` | 1 | _patch_widgets, monkeypatch |
| `test_the_gap_between_keys_divides_the_list_rather_than_ending_it` | 1 | _patch_widgets, monkeypatch |
| `test_the_pad_steps_the_module_rows_without_choosing_one` | 1 | _patch_widgets, monkeypatch |
| `test_the_pad_starts_from_the_row_the_dot_is_on` | 1 | _patch_widgets, monkeypatch |
| `test_the_pad_lands_on_the_first_row_where_nothing_is_chosen_yet` | 2 | _patch_widgets, delta, monkeypatch |
| `test_the_pad_stops_at_either_end_of_the_list` | 1 | _patch_widgets, monkeypatch |
| `test_a_marked_row_is_chosen_exactly_as_a_tap_would_choose_it` | 1 | _patch_widgets, monkeypatch |
| `test_a_highlight_that_never_moved_marks_nothing` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_marked_with_right_is_come_back_to_with_b` | 1 | _patch_widgets, monkeypatch |
| `test_a_left_press_with_nothing_marked_abandons_the_move` | 1 | _patch_widgets, monkeypatch |
| `test_a_revert_is_one_mark_deep` | 1 | _patch_widgets, monkeypatch |
| `test_a_page_turned_is_as_far_back_as_a_revert_reaches` | 1 | _patch_widgets, monkeypatch |
| `test_the_pad_chooses_a_mode_and_can_put_it_back` | 1 | _patch_widgets, monkeypatch |
| `test_the_pad_goes_on_from_the_row_it_marked` | 1 | _patch_widgets, monkeypatch |
| `test_the_right_key_chooses_the_module_and_turns_the_page` | 1 | _patch_widgets, monkeypatch |
| `test_the_right_key_turns_the_page_where_the_highlight_never_moved` | 1 | _patch_widgets, monkeypatch |
| `test_the_right_key_goes_nowhere_until_a_module_is_chosen` | 1 | _patch_widgets, monkeypatch |
| `test_the_right_key_chooses_a_mode_without_turning_the_id_page` | 1 | _patch_widgets, monkeypatch |
| `test_the_right_key_turns_the_page_on_a_modules_only_setting` | 1 | _patch_widgets, monkeypatch |
| `test_a_setting_below_the_one_marked_holds_the_page` | 1 | _patch_widgets, monkeypatch |
| `test_the_a_key_chooses_the_highlighted_row_and_turns_the_page` | 1 | _patch_widgets, monkeypatch |
| `test_the_a_key_turns_the_page_where_nothing_was_highlighted` | 1 | _patch_widgets, monkeypatch |
| `test_the_a_key_goes_nowhere_until_a_module_is_chosen` | 1 | _patch_widgets, monkeypatch |
| `test_the_a_key_presses_configure_on_the_review_page` | 1 | _patch_widgets, monkeypatch |
| `test_the_a_key_sends_nothing_where_configure_is_disabled` | 1 | _patch_widgets, monkeypatch |
| `test_the_b_key_turns_back_a_page_and_stops_at_the_first` | 1 | _patch_widgets, monkeypatch |
| `test_the_stick_moves_the_page_and_chooses_nothing` | 1 | _patch_widgets, monkeypatch |
| `test_a_page_with_nowhere_to_go_answers_the_stick_with_nothing` | 1 | _patch_widgets, monkeypatch |
| `test_a_panel_with_no_window_yet_is_safe_to_scroll` | 1 | _patch_widgets, monkeypatch |
| `test_the_pad_ticks_and_clears_the_only_setting_a_bpc2_has` | 1 | _patch_widgets, monkeypatch |
| `test_the_pad_steps_the_sensor_tracks_actions` | 1 | _patch_widgets, monkeypatch |
| `test_the_pad_leaves_a_setting_the_page_has_disabled_alone` | 1 | _patch_widgets, monkeypatch |
| `test_the_pad_does_nothing_on_the_review_page` | 1 | _patch_widgets, monkeypatch |
| `test_the_pad_does_nothing_while_the_id_is_being_typed` | 1 | _patch_widgets, monkeypatch |
| `test_every_list_the_pad_steps_shows_where_it_is_where_there_is_a_pad` | 2 | _patch_widgets, deck, monkeypatch |
| `test_the_highlight_is_armed_on_the_deck_rather_than_on_an_appliance` | 2 | _patch_widgets, linux, monkeypatch |
| `test_the_panel_opens_with_no_row_highlighted` | 1 | _patch_widgets, monkeypatch |
| `test_the_pad_keys_ask_the_same_questions_the_nav_buttons_do` | 1 | _patch_widgets, monkeypatch |
| `test_the_pages_are_drawn_in_a_window_and_the_buttons_below_it` | 1 | _patch_widgets, monkeypatch |
| `test_the_bar_is_drawn_wide_enough_to_be_seen_and_wider_where_there_is_room` | 2 | _patch_widgets, deck, expected, monkeypatch |
| `test_no_bar_is_drawn_over_anything_the_page_has_written` | 2 | _patch_widgets, deck, monkeypatch |
| `test_a_bar_is_drawn_wide_enough_to_be_worked_and_wider_where_there_is_width` | 1 | _patch_widgets, monkeypatch |
| `test_a_page_is_come_to_at_its_top_and_the_window_re_fitted_for_it` | 1 | _patch_widgets, monkeypatch |
| `test_the_window_is_given_the_room_the_popup_leaves_it` | 1 | _patch_widgets, monkeypatch |
| `test_the_window_asks_again_whenever_what_is_in_it_changes_size` | 1 | _patch_widgets, monkeypatch |
| `test_every_line_the_panel_writes_is_broken_at_the_pane` | 1 | _patch_widgets, monkeypatch |
| `test_a_name_is_broken_inside_its_own_column_and_not_at_the_page` | 1 | _patch_widgets, monkeypatch |
| `test_a_name_is_left_the_page_less_what_the_columns_beside_it_take` | 1 | _patch_widgets, monkeypatch |
| `test_the_listing_leaves_its_last_column_the_page_less_the_three_beside_it` | 1 | _patch_widgets, monkeypatch |
| `test_the_configuration_column_keeps_a_share_of_the_row_where_the_reservation_would_swallow_it` | 1 | _patch_widgets, monkeypatch |
| `test_a_name_keeps_a_share_of_the_row_on_a_pane_too_narrow_to_reserve_from` | 1 | _patch_widgets, monkeypatch |
| `test_every_row_the_panel_draws_is_broken_inside_the_pane` | 1 | _patch_widgets, monkeypatch |
| `test_a_row_is_left_the_pane_less_what_it_spends_before_its_text` | 1 | _patch_widgets, monkeypatch |
| `test_a_row_keeps_a_floor_of_room_on_a_host_that_has_measured_nothing` | 1 | _patch_widgets, monkeypatch |
| `test_the_mode_rows_are_sized_against_every_row_they_can_show` | 1 | _patch_widgets, monkeypatch |
| `test_the_module_rows_are_fitted_a_step_above_the_mode_rows` | 1 | _patch_widgets, monkeypatch |
| `test_every_mode_label_is_a_row_a_module_can_show_at_its_widest` | 1 | _patch_widgets, monkeypatch |
| `test_the_pad_brings_the_row_it_steps_onto_into_view` | 1 | _patch_widgets, monkeypatch |
| `test_a_step_that_moves_nothing_scrolls_nothing` | 1 | _patch_widgets, monkeypatch |
| `test_the_pi_is_the_pane_with_nothing_to_spare` | 3 | _patch_widgets, cramped, deck, linux, monkeypatch |
| `test_the_titled_boxes_and_their_rows_read_at_one_size` | 1 | _patch_widgets, monkeypatch |
| `test_the_listing_names_every_module_the_layout_reports` | 1 | _patch_widgets, monkeypatch |
| `test_the_listing_calls_the_ir_sensor_track_the_ir` | 1 | _patch_widgets, monkeypatch |
| `test_the_last_column_says_what_a_module_is_set_to` | 1 | _patch_widgets, monkeypatch |
| `test_a_mode_named_for_nothing_but_the_remote_key_is_left_unsaid` | 1 | _patch_widgets, monkeypatch |
| `test_a_block_of_one_address_is_left_to_the_id_column` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_with_nothing_of_its_own_to_say_says_nothing` | 1 | _patch_widgets, monkeypatch |
| `test_a_flag_the_module_reports_as_off_is_written_as_off` | 1 | _patch_widgets, monkeypatch |
| `test_the_listing_says_on_one_line_what_the_options_page_says_in_a_sentence` | 1 | _patch_widgets, monkeypatch |
| `test_the_motor_a_setting_belongs_to_is_named_once` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_whose_settings_are_one_block_is_written_as_one` | 1 | _patch_widgets, monkeypatch |
| `test_the_configuration_column_says_nothing_about_the_module_firmware` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_that_has_not_said_which_mode_it_is_in_says_so` | 1 | _patch_widgets, monkeypatch |
| `test_the_listing_is_ordered_by_the_key_the_operator_chooses` | 3 | _patch_widgets, expected, monkeypatch, sort_key |
| `test_the_key_the_page_opens_on_is_the_one_the_rows_show` | 1 | _patch_widgets, monkeypatch |
| `test_a_key_the_page_does_not_offer_leaves_the_order_alone` | 1 | _patch_widgets, monkeypatch |
| `test_the_listing_is_written_into_a_grid_under_its_headings` | 1 | _patch_widgets, monkeypatch |
| `test_every_cell_is_filled_to_its_column_and_stands_at_the_top_of_its_row` | 1 | _patch_widgets, monkeypatch |
| `test_the_cells_are_stood_up_again_after_a_re_order` | 1 | _patch_widgets, monkeypatch |
| `test_a_modules_row_is_drawn_on_a_wash_and_the_headings_are_not` | 1 | _patch_widgets, monkeypatch |
| `test_the_configuration_cell_is_washed_block_by_block` | 1 | _patch_widgets, monkeypatch |
| `test_the_rows_are_held_apart_by_white_space_and_the_columns_are_not` | 1 | _patch_widgets, monkeypatch |
| `test_the_columns_are_held_apart_inside_the_cells_where_the_wash_covers_it` | 1 | _patch_widgets, monkeypatch |
| `test_the_module_rows_keep_a_plain_cells_padding` | 1 | _patch_widgets, monkeypatch |
| `test_the_listing_reads_at_the_page_body_size_on_every_screen` | 2 | _patch_widgets, cramped, linux, monkeypatch |
| `test_a_group_of_settings_begins_a_few_pixels_below_the_one_above_it` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_with_one_group_of_settings_has_nothing_to_hold_apart` | 1 | _patch_widgets, monkeypatch |
| `test_the_blocks_of_a_cell_are_spaced_again_after_a_re_order` | 1 | _patch_widgets, monkeypatch |
| `test_a_block_left_over_from_a_fuller_module_is_taken_off_the_page` | 1 | _patch_widgets, monkeypatch |
| `test_a_row_the_page_is_no_longer_showing_is_left_where_it_is` | 1 | _patch_widgets, monkeypatch |
| `test_a_row_left_over_from_a_fuller_layout_is_taken_off_the_page` | 1 | _patch_widgets, monkeypatch |
| `test_a_layout_that_has_reported_nothing_says_so_rather_than_showing_a_bare_grid` | 1 | _patch_widgets, monkeypatch |
| `test_the_listing_is_read_afresh_each_time_it_is_opened` | 1 | _patch_widgets, monkeypatch |
| `test_the_key_that_opens_the_listing_stands_left_of_next` | 1 | _patch_widgets, monkeypatch |
| `test_the_key_that_opens_the_listing_is_shown_on_the_first_page_alone` | 1 | _patch_widgets, monkeypatch |
| `test_the_listing_is_left_by_back_for_the_page_it_was_opened_from` | 1 | _patch_widgets, monkeypatch |
| `test_next_never_walks_into_the_listing` | 1 | _patch_widgets, monkeypatch |
| `test_the_pad_works_the_sort_keys_and_turns_no_page_with_them` | 1 | _patch_widgets, monkeypatch |
| `test_a_row_of_the_listing_opens_the_id_page_on_the_module_it_names` | 1 | _patch_widgets, monkeypatch |
| `test_a_row_opens_on_the_mode_its_own_module_is_running_in` | 1 | _patch_widgets, monkeypatch |
| `test_a_press_anywhere_in_a_row_opens_it` | 1 | _patch_widgets, monkeypatch |
| `test_the_headings_of_the_listing_are_no_row_to_open` | 1 | _patch_widgets, monkeypatch |
| `test_a_row_is_bound_afresh_rather_than_bound_again` | 1 | _patch_widgets, monkeypatch |
| `test_a_row_left_over_from_a_fuller_layout_opens_nothing` | 1 | _patch_widgets, monkeypatch |
| `test_a_row_opens_on_the_module_the_page_is_showing_after_a_re_order` | 1 | _patch_widgets, monkeypatch |
| `test_the_module_a_row_opens_is_seeded_with_its_own_settings` | 1 | _patch_widgets, monkeypatch |
| `test_opening_a_module_from_its_row_is_not_seeded_over_by_a_late_store` | 1 | _patch_widgets, monkeypatch |
| `test_a_module_the_panel_cannot_program_has_nothing_to_open` | 1 | _patch_widgets, monkeypatch |
| `test_the_listing_is_left_behind_by_the_row_that_was_tapped` | 1 | _patch_widgets, monkeypatch |

## tests/gui/test_lcs_device_registry.py

90 cases; 84 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestRegistryShape::test_the_registry_knows_five_modules` | 1 |  |
| `TestRegistryShape::test_every_one_of_them_can_be_programmed` | 1 |  |
| `TestRegistryShape::test_they_are_offered_in_name_order` | 1 |  |
| `TestRegistryShape::test_the_recognition_order_is_left_alone` | 1 |  |
| `TestRegistryShape::test_every_mode_is_complete` | 1 |  |
| `TestRegistryShape::test_asc2_has_four_modes` | 1 |  |
| `TestRegistryShape::test_bpc2_one_id_modes_are_reserved` | 1 |  |
| `TestRegistryShape::test_stm2_modes` | 1 |  |
| `TestRegistryShape::test_pdi_devices` | 1 |  |
| `TestSensorTrack::test_single_acc_mode` | 1 |  |
| `TestSensorTrack::test_action_choices_track_sensor_track_opts` | 1 |  |
| `TestSensorTrack::test_default_action_is_no_action` | 1 |  |
| `TestSensorTrack::test_the_action_command_is_reported_as_the_sequence_of_the_config_record` | 1 |  |
| `TestReportedFields::test_an_option_is_reported_on_its_own_key_unless_another_field_is_named` | 1 |  |
| `TestReportedFields::test_every_option_is_reported_on_a_field_its_module_really_carries` | 1 |  |
| `TestReportedFields::test_a_setting_reported_one_level_down_is_read_through_the_whole_path` | 1 |  |
| `TestReportedFields::test_an_option_that_names_no_field_is_read_by_its_own_key` | 1 |  |
| `TestReportedFields::test_a_path_that_runs_out_partway_reports_nothing` | 1 |  |
| `TestReportedMode::test_a_module_is_asked_on_the_field_it_names` | 1 |  |
| `TestReportedMode::test_a_module_says_its_mode_on_the_mode_byte_unless_another_field_is_named` | 1 |  |
| `TestReportedMode::test_a_record_that_says_nothing_reports_no_mode` | 1 |  |
| `TestReportedMode::test_a_flag_is_not_a_mode` | 1 |  |
| `TestMaxBase::test_max_base` | 7 | device, expected, mode_key |
| `TestMaxBase::test_never_above_98` | 1 |  |
| `TestAmc2::test_it_is_in_the_registry` | 1 |  |
| `TestAmc2::test_it_is_offered_as_a_choice` | 1 |  |
| `TestAmc2::test_it_is_recognized_from_its_own_state_flag` | 1 |  |
| `TestAmc2::test_the_accessory_key_is_the_only_one_it_is_offered_on` | 1 |  |
| `TestAmc2::test_the_two_keys_it_will_not_be_programmed_onto_are_written_down_anyway` | 1 |  |
| `TestAmc2::test_every_mode_is_one_of_the_address_types_the_module_reports` | 1 |  |
| `TestAmc2::test_both_motors_are_set_up_in_the_one_gesture` | 1 |  |
| `TestAmc2::test_the_accessory_sequence_is_the_flowchart_in_order` | 1 |  |
| `TestAmc2::test_the_r_key_is_tapped_only_for_a_motor_that_is_to_remember` | 1 |  |
| `TestAmc2::test_each_motor_is_entered_under_its_own_aux_key` | 1 |  |
| `TestAmc2::test_the_digit_pressed_is_the_reported_setting_counted_from_one` | 1 |  |
| `TestLookups::test_device_for_key` | 1 |  |
| `TestLookups::test_device_for_state` | 1 |  |
| `TestLookups::test_devices_for_state_names_every_module_a_shared_record_identifies` | 1 |  |
| `TestLookups::test_device_for_pdi_device` | 1 |  |
| `TestLookups::test_mode_for_pdi_mode` | 1 |  |
| `TestLookups::test_default_mode_skips_disabled` | 1 |  |
| `TestLookups::test_unknown_option_raises` | 1 |  |
| `TestLookups::test_a_module_with_no_modes_says_why_rather_than_raising_index_error` | 1 |  |
| `TestDigitKeys::test_an_accessory_presses_the_accessory_keys` | 1 |  |
| `TestDigitKeys::test_an_engine_and_a_train_are_the_same_handset_keys` | 1 |  |
| `TestDigitKeys::test_a_number_is_one_command_carrying_the_digit_as_its_data` | 1 |  |
| `TestDigitKeys::test_there_is_no_third_aux_key` | 1 |  |
| `TestDigitKeys::test_a_digit_is_one_of_the_ten_on_the_handset` | 1 |  |
| `TestDigitKeys::test_a_switch_is_programmed_with_neither` | 1 |  |
| `TestPressSequences::test_every_offered_mode_presses_from_its_modules_own_defaults` | 1 |  |
| `TestPressSequences::test_a_gesture_that_enters_a_digit_is_two_presses_and_every_other_is_one` | 1 |  |
| `TestProgrammedOptions::test_a_setting_is_named_by_the_press_that_sends_it` | 1 |  |
| `TestProgrammedOptions::test_every_offered_mode_sets_all_of_its_modules_settings` | 1 |  |
| `TestProgrammedOptions::test_a_mode_that_sends_nothing_but_an_address_sets_nothing` | 1 |  |
| `TestTmccIdText::test_a_block_is_named_by_its_two_ends` | 1 |  |
| `TestTmccIdText::test_a_single_address_is_named_once` | 1 |  |
| `TestTmccIdText::test_an_end_below_the_base_is_a_single_address` | 1 |  |
| `TestTmccIdText::test_a_count_is_a_digit` | 1 |  |
| `TestTmccIdText::test_one_address_is_never_plural` | 1 |  |
| `TestTmccIdText::test_more_than_one_address_always_is` | 1 |  |
| `TestTmccIdText::test_what_is_counted_is_always_a_tmcc_id` | 1 |  |
| `TestTmccIdText::test_a_span_is_the_same_block_with_the_words_left_off` | 1 |  |
| `TestTmccIdText::test_a_span_of_one_address_is_that_address_alone` | 1 |  |
| `TestModeNames::test_every_offered_mode_is_named` | 1 |  |
| `TestModeNames::test_no_two_modes_a_module_offers_are_named_alike` | 1 |  |
| `TestModeNames::test_a_name_opens_with_its_cab_key` | 1 |  |
| `TestModeNames::test_a_key_is_spelled_one_way_throughout` | 1 |  |
| `TestModeNames::test_a_name_is_a_key_and_at_most_one_qualifier` | 1 |  |
| `TestModeNames::test_a_mode_is_qualified_exactly_when_its_key_offers_a_choice` | 1 |  |
| `TestModeNames::test_a_qualifier_is_one_word` | 1 |  |
| `TestModeNames::test_the_asc2_accessory_modes_are_told_apart_by_what_they_are_for` | 1 |  |
| `TestModeNames::test_a_name_counts_nothing` | 1 |  |
| `TestModeNames::test_the_asc2_switch_modes_key_keeps_a_word_the_operator_never_reads` | 1 |  |
| `TestModeNames::test_a_name_says_nothing_a_mode_does_besides_claiming_addresses` | 1 |  |
| `TestModeLabels::test_every_mode_names_the_block_it_would_claim` | 1 |  |
| `TestModeLabels::test_every_mode_names_the_count_it_claims` | 1 |  |
| `TestModeLabels::test_a_block_follows_the_address_it_is_based_at` | 1 |  |
| `TestModeLabels::test_a_mode_is_offered_at_the_highest_base_it_fits` | 1 |  |
| `TestModeLabels::test_an_id_is_always_a_tmcc_id` | 1 |  |
| `TestModeLabels::test_a_count_is_a_digit` | 1 |  |
| `TestModeLabels::test_a_counted_label_agrees_with_the_mode` | 1 |  |
| `TestModeLabels::test_the_longest_row_is_the_stm2s_widest_block` | 1 |  |
| `TestModeLabels::test_a_block_covers_exactly_the_ids_the_mode_claims` | 1 |  |
| `TestModeLabels::test_every_switch_mode_names_the_ids_it_consumes` | 1 |  |

## tests/gui/test_lcs_icons.py

5 cases; 3 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_the_icon_asset_is_present_and_loadable` | 3 | name |
| `test_the_return_key_icon_map_covers_both_lcs_panels` | 1 |  |
| `test_the_navigation_key_labels_carry_their_ellipses` | 1 |  |

## tests/gui/test_lcs_id_map.py

62 cases; 62 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestOccupantOf::test_base_hit` | 1 |  |
| `TestOccupantOf::test_interior_port_hit` | 1 |  |
| `TestOccupantOf::test_last_port_hit` | 1 |  |
| `TestOccupantOf::test_unowned_id` | 1 |  |
| `TestOccupantOf::test_empty_store` | 1 |  |
| `TestOccupantOf::test_non_lcs_state_ignored` | 1 |  |
| `TestOccupantOf::test_sensor_track_single_port` | 1 |  |
| `TestOccupantOf::test_switch_and_train_scopes` | 1 |  |
| `TestBlockSize::test_num_ids_overrides_registry_default` | 1 |  |
| `TestBlockSize::test_registry_default_when_info_missing` | 1 |  |
| `TestBlockSize::test_unknown_mode_falls_back_to_one_port` | 1 |  |
| `TestOverlaps::test_detects_overlap` | 1 |  |
| `TestOverlaps::test_no_overlap_when_blocks_are_disjoint` | 1 |  |
| `TestOverlaps::test_ignore_base_omits_the_module_being_reconfigured` | 1 |  |
| `TestScope::test_scope_picks_between_two_modules_on_the_same_number` | 1 |  |
| `TestScope::test_the_switch_block_extends_past_the_accessory_on_its_base` | 1 |  |
| `TestScope::test_omitting_the_scope_still_returns_every_module` | 1 |  |
| `TestScope::test_effective_scope_comes_from_the_registry_not_the_store` | 1 |  |
| `TestScope::test_the_store_scope_is_the_fallback_when_the_mode_is_unknown` | 1 |  |
| `TestScope::test_overlaps_only_reports_blocks_on_the_same_key` | 1 |  |
| `TestScope::test_the_same_module_kind_on_two_keys_is_two_modules` | 1 |  |
| `TestSeveralModulesOnOneId::test_every_module_on_the_id_is_returned` | 1 |  |
| `TestSeveralModulesOnOneId::test_occupant_of_still_answers_with_the_first` | 1 |  |
| `TestSeveralModulesOnOneId::test_a_module_the_panel_cannot_program_is_still_recognized` | 1 | monkeypatch |
| `TestSeveralModulesOnOneId::test_an_amc2_that_has_not_reported_yet_holds_one_id` | 1 |  |
| `TestSeveralModulesOnOneId::test_nothing_there_is_an_empty_list` | 1 |  |
| `TestPdiDeviceStore::test_both_modules_on_the_shared_id_are_reported` | 1 |  |
| `TestPdiDeviceStore::test_each_module_is_sized_from_its_own_config` | 1 |  |
| `TestPdiDeviceStore::test_the_shared_records_own_size_no_longer_wins` | 1 |  |
| `TestPdiDeviceStore::test_interior_ids_of_the_true_block_are_claimed` | 1 |  |
| `TestPdiDeviceStore::test_a_modules_own_mode_decides_its_remote_key` | 1 |  |
| `TestPdiDeviceStore::test_a_switch_mode_asc2_is_a_switch_however_it_was_filed` | 1 |  |
| `TestPdiDeviceStore::test_the_component_state_is_carried_for_seeding` | 1 |  |
| `TestPdiDeviceStore::test_the_config_packet_itself_is_carried_for_seeding_too` | 1 |  |
| `TestPdiDeviceStore::test_a_store_whose_entries_are_the_packets_is_read_as_it_stands` | 1 |  |
| `TestPdiDeviceStore::test_a_module_only_the_states_know_has_no_config_record` | 1 |  |
| `TestPdiDeviceStore::test_a_module_only_the_states_know_is_still_reported` | 1 |  |
| `TestPdiDeviceStore::test_a_module_is_never_listed_twice` | 1 |  |
| `TestPdiDeviceStore::test_overlaps_use_the_true_block_too` | 1 |  |
| `TestPdiDeviceStore::test_an_empty_pdi_store_changes_nothing` | 1 |  |
| `TestAmc2Address::test_an_amc2_holds_the_address_the_key_its_access_type_names` | 1 |  |
| `TestAmc2Address::test_an_accessory_amc2_holds_exactly_one_id` | 1 |  |
| `TestTrains::test_every_train_is_reported_base_first` | 1 |  |
| `TestTrains::test_a_train_holds_the_one_address_it_is_numbered_at` | 1 |  |
| `TestTrains::test_a_train_the_base_has_named_is_named_for_its_road` | 1 |  |
| `TestTrains::test_a_train_with_a_number_and_no_road_name_is_still_named_something` | 1 |  |
| `TestTrains::test_a_train_with_a_road_name_and_no_number_is_named_for_the_road_alone` | 1 |  |
| `TestTrains::test_a_train_nobody_has_named_is_called_what_it_is` | 1 |  |
| `TestTrains::test_a_train_with_nothing_to_say_at_all_is_still_called_something` | 1 |  |
| `TestTrains::test_a_module_filed_with_the_trains_is_not_one_of_them` | 1 |  |
| `TestTrains::test_a_module_this_pass_does_not_know_is_not_a_train_either` | 1 |  |
| `TestTrains::test_only_the_trains_own_key_is_read` | 1 |  |
| `TestTrains::test_an_address_out_of_range_is_no_train` | 1 |  |
| `TestTrains::test_a_name_the_base_reported_as_both_halves_reads_as_the_gui_reads_it` | 1 |  |
| `TestTrains::test_a_train_reported_twice_is_reported_once` | 1 |  |
| `TestTrains::test_the_trains_inside_a_block_are_the_ones_it_would_take` | 1 |  |
| `TestTrains::test_a_block_of_one_takes_the_address_it_is_based_at` | 1 |  |
| `TestTrains::test_the_train_at_one_address_can_be_left_out` | 1 |  |
| `TestTrains::test_no_store_built_is_not_an_error` | 1 | monkeypatch |
| `TestStoreDefault::test_no_store_built_is_not_an_error` | 1 | monkeypatch |
| `TestStoreDefault::test_a_pdi_store_alone_is_enough` | 1 | monkeypatch |
| `TestStoreDefault::test_a_pdi_store_that_was_never_built_is_not_an_error` | 1 | monkeypatch |

## tests/gui/test_lcs_imports.py

20 cases; 5 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_no_lcs_module_imports_the_package_root` | 6 | module |
| `test_every_lcs_project_import_is_relative` | 6 | module |
| `test_every_lcs_project_import_stays_inside_the_package` | 6 | module |
| `test_the_panel_takes_is_linux_from_the_leaf_module` | 1 |  |
| `test_the_package_root_re_exports_the_same_is_linux` | 1 |  |

## tests/gui/test_lcs_panel_wiring.py

4 cases; 4 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_the_lcs_key_opens_a_panel_seeded_from_what_is_on_screen` | 1 | _patch_panel, monkeypatch |
| `test_the_panel_is_built_once_and_re_seeded_on_every_press` | 1 | _patch_panel, monkeypatch |
| `test_the_key_pressed_in_entry_mode_opens_the_panel_with_nothing_selected` | 1 | _patch_panel, monkeypatch |
| `test_the_keypad_key_binds_straight_to_the_panes_opener` | 1 | _patch_panel, monkeypatch |

## tests/gui/test_lcs_sequence_builder.py

50 cases; 33 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestAsc2::test_acc_eight_id` | 1 |  |
| `TestAsc2::test_acc_single_id` | 1 |  |
| `TestAsc2::test_sw_momentary` | 1 |  |
| `TestAsc2::test_sw_latching` | 1 |  |
| `TestBpc2::test_train_restore_on` | 1 |  |
| `TestBpc2::test_train_restore_off_omits_coupler` | 1 |  |
| `TestBpc2::test_restore_defaults_off` | 1 |  |
| `TestBpc2::test_accessory_scope` | 1 |  |
| `TestBpc2::test_train_digit_is_entered_on_the_engine_keys` | 1 |  |
| `TestStm2::test_single_wire` | 1 |  |
| `TestStm2::test_two_wire` | 1 |  |
| `TestSensorTrack::test_every_action` | 10 | digit |
| `TestSensorTrack::test_action_press_never_omitted_by_default` | 1 |  |
| `TestAmc2::test_acc_sequence_follows_the_flowchart` | 1 |  |
| `TestAmc2::test_each_motor_is_entered_under_its_own_aux_key` | 1 |  |
| `TestAmc2::test_motor_mode_is_pressed_as_the_manual_numbers_it` | 3 | digit, output_type |
| `TestAmc2::test_each_motor_remembers_independently` | 4 | motor1_restore, motor2_restore |
| `TestAmc2::test_untouched_options_still_send_both_motor_modes` | 1 |  |
| `TestAmc2::test_display_names_the_motor_each_gesture_is_for` | 1 |  |
| `TestAmc2::test_modes_the_panel_will_not_offer_still_build` | 2 | key, scope |
| `TestDigitGestures::test_aux_key_is_sent_first_and_the_number_after_it` | 1 |  |
| `TestDigitGestures::test_number_key_carries_the_digit_as_its_data` | 1 |  |
| `TestDigitGestures::test_both_keys_are_addressed_to_the_module_being_programmed` | 1 |  |
| `TestVerifyAndDisplay::test_verify_requests` | 1 |  |
| `TestVerifyAndDisplay::test_display_order_matches_presses` | 1 |  |
| `TestVerifyAndDisplay::test_display_counts_gestures_while_presses_count_keys` | 1 |  |
| `TestVerifyAndDisplay::test_a_program_remembers_the_option_values_it_was_built_from` | 1 |  |
| `TestVerifyAndDisplay::test_a_program_for_a_module_with_no_settings_remembers_none` | 1 |  |
| `TestVerifyAndDisplay::test_program_instruction` | 1 |  |
| `TestValidation::test_mode_must_belong_to_device` | 1 |  |
| `TestValidation::test_bad_base_id` | 3 | base_id |
| `TestValidation::test_base_id_above_max_base` | 1 |  |
| `TestValidation::test_required_option_missing` | 1 |  |

## tests/gui/test_motors_gui.py

17 cases; 17 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_make_state_button_hides_level_box_below_480px` | 1 | _patch_widgets, monkeypatch |
| `test_make_state_button_keeps_level_box_at_or_above_480px` | 1 | _patch_widgets, monkeypatch |
| `test_slider_height_increases_when_level_box_removed` | 1 | _patch_widgets, monkeypatch |
| `test_toggle_motor_state_off_at_zero_sets_level_to_100` | 1 | _patch_widgets, monkeypatch |
| `test_toggle_motor_state_on_uses_regular_toggle_behavior` | 1 | _patch_widgets, monkeypatch |
| `test_toggle_lamp_zero_turns_on_to_100` | 1 | _patch_widgets, monkeypatch |
| `test_toggle_lamp_100_off_sets_ui_to_zero_then_on_sets_100_when_state_is_zero` | 1 | _patch_widgets, monkeypatch |
| `test_level_box_uses_screen_height_not_container_height` | 1 | _patch_widgets, monkeypatch |
| `test_level_box_hidden_when_screen_height_is_below_threshold` | 1 | _patch_widgets, monkeypatch |
| `test_level_box_hidden_when_screen_metric_unavailable_but_window_is_short` | 1 | _patch_widgets, monkeypatch |
| `test_level_box_hidden_when_window_is_short_even_if_screen_reports_tall` | 1 | _patch_widgets, monkeypatch |
| `test_lamp_slider_release_to_zero_sets_button_off_and_sends_value` | 1 | _patch_widgets, monkeypatch |
| `test_external_lamp_change_updates_slider_even_when_focused` | 1 | _patch_widgets, monkeypatch |
| `test_external_lamp_zero_change_updates_slider_and_sets_off_color` | 1 | _patch_widgets, monkeypatch |
| `test_external_motor_change_updates_slider_and_color` | 1 | _patch_widgets, monkeypatch |
| `test_lamp_trough_follows_actual_level_even_when_button_forced_on` | 1 | _patch_widgets, monkeypatch |
| `test_state_change_callback_uses_tmcc_id_and_updates_visible_outputs` | 1 | _patch_widgets, monkeypatch |

## tests/gui/test_pycab_app.py

16 cases; 10 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_icons_load_from_package_resources_with_explicit_master` | 2 | large, monkeypatch, size, tmp_path, tmp_path_factory |
| `test_unavailable_icon_does_not_prevent_confirmation` | 2 | caplog, error, monkeypatch |
| `test_logo_label_retains_its_photo` | 1 | monkeypatch |
| `test_missing_logo_leaves_dialog_usable` | 1 | monkeypatch |
| `test_app_sets_and_retains_both_window_icons` | 2 | monkeypatch, supported |
| `test_app_still_starts_when_both_icons_are_unavailable` | 1 | monkeypatch |
| `test_yesno_uses_branded_dialog_and_returns_a_boolean` | 3 | monkeypatch, result |
| `test_confirmation_body_displays_logo_and_message` | 1 | monkeypatch |
| `test_confirmation_buttons_have_safe_default_and_keyboard_bindings` | 1 | monkeypatch |
| `test_return_requires_explicit_yes_focus` | 2 | yes_focused |

## tests/gui/test_route_builder_panel.py

300 cases; 106 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_widget_callbacks_are_created_on_demand_and_isolated` | 3 | callback_name |
| `test_deck_analog_scrolls_picker_without_selecting_or_driving` | 6 | context, deck_picker, monkeypatch, panel, target |
| `test_deck_touchpad_scrolls_picker_and_cards_without_changing_route` | 1 | deck_picker, monkeypatch, panel |
| `test_deck_analog_scroll_stops_when_picker_is_unavailable` | 4 | deck_picker, monkeypatch, panel, stop |
| `test_route_controller_scroll_clamps_and_preserves_small_movements` | 1 | deck_picker, monkeypatch, panel |
| `test_route_metadata_editing_consumes_analog_input_without_scrolling` | 2 | deck_picker, field_name, monkeypatch, panel |
| `test_deck_picker_browses_without_selecting_and_reveals_complete_rows` | 1 | deck_picker, monkeypatch, panel |
| `test_deck_picker_browses_mixed_choices_without_changing_sort` | 8 | deck_picker, descending, filter_name, monkeypatch, panel, sort |
| `test_deck_picker_selects_clears_and_adds_highlighted_not_previous_choice` | 3 | context, deck_picker, monkeypatch, panel |
| `test_deck_picker_right_adds_highlighted_not_previous_choice` | 6 | context, deck_picker, monkeypatch, panel, scope |
| `test_deck_picker_x_cancels_only_add_and_reopening_resets_cursor` | 2 | button, deck_picker, monkeypatch, name, panel |
| `test_deck_picker_a_selects_and_adds_without_prior_dpad_press` | 2 | button, deck_picker, monkeypatch, name, panel |
| `test_deck_picker_cursor_tracks_touch_sort_and_filter_without_stale_selection` | 1 | deck_picker, monkeypatch, panel |
| `test_deck_picker_repeats_at_catalog_cadence_and_stops_on_release` | 1 | deck_picker, monkeypatch, panel |
| `test_deck_picker_stops_held_navigation_when_no_longer_available` | 5 | deck_picker, monkeypatch, panel, stop |
| `test_deck_picker_search_editing_blocks_selection_but_allows_cancel_and_halt` | 2 | cancel_button, cancel_name, deck_picker, monkeypatch, panel |
| `test_deck_picker_stops_commands_held_before_opening` | 3 | button, deck_picker, monkeypatch, name, panel |
| `test_deck_picker_highlight_does_not_check_radio_or_replace_active_green` | 1 | deck_picker, monkeypatch, panel |
| `test_deck_picker_a_keeps_existing_component_validation` | 4 | button, deck_picker, invalid, monkeypatch, name, panel |
| `test_picker_size_and_page_navigation_follow_available_layout` | 7 | available, bar_width, compact, height, monkeypatch, panel, system, width |
| `test_picker_scrollbar_replaces_page_buttons_and_matches_scroll_box` | 2 | compact, monkeypatch, panel |
| `test_picker_refresh_resets_scrollbar_and_keeps_selection_rules` | 5 | action, monkeypatch, panel |
| `test_picker_scrollbar_arrows_move_one_row_without_selecting` | 2 | desktop, monkeypatch, panel |
| `test_steam_deck_picker_fits_four_touch_rows_in_original_height` | 1 | monkeypatch, panel |
| `test_picker_resize_uses_whole_rows_without_changing_entry_height` | 6 | monkeypatch, panel, remainder, rows |
| `test_picker_resize_preserves_selection_and_clamps_scroll_position` | 1 | monkeypatch, panel |
| `test_picker_resize_accounts_for_changes_to_controls_and_is_stable` | 1 | monkeypatch, panel |
| `test_picker_resize_ignores_unavailable_geometry` | 4 | monkeypatch, panel, unavailable |
| `test_picker_resize_is_scheduled_once_for_geometry_changes` | 1 | monkeypatch, panel |
| `test_steam_deck_picker_aligns_inline_details_and_truncates_long_names` | 2 | filter_name, monkeypatch, panel |
| `test_desktop_picker_double_click_adds_scrolled_component_and_returns_to_main` | 4 | desktop_panel, filter_name, monkeypatch, panel |
| `test_desktop_picker_double_click_outside_rows_does_not_add_selection` | 6 | desktop_panel, location, monkeypatch, panel |
| `test_desktop_picker_double_click_keeps_validation_errors_in_picker` | 6 | desktop_panel, monkeypatch, panel, unavailable |
| `test_double_click_is_limited_to_desktop_picker` | 6 | compact, monkeypatch, panel, platform |
| `test_desktop_picker_keys_select_and_reveal_without_adding` | 2 | desktop_panel, monkeypatch, panel |
| `test_desktop_picker_keys_use_current_filter_sort_and_scope` | 4 | desktop_panel, expected_scope, filter_name, monkeypatch, panel |
| `test_desktop_card_keys_browse_without_reordering_or_editing` | 2 | desktop_panel, monkeypatch, panel |
| `test_desktop_lists_receive_focus_without_stealing_inline_edits` | 2 | desktop_panel, monkeypatch, panel |
| `test_touch_lists_keep_touch_bindings_without_desktop_focus` | 1 | monkeypatch, panel |
| `test_desktop_wheel_browses_both_lists` | 20 | delta, desktop_panel, horizontal, monkeypatch, panel, units |
| `test_mac_touch_surface_scrolls_by_pixels_without_editing` | 36 | desktop_panel, dx, dy, horizontal, monkeypatch, panel, signed |
| `test_mac_touch_surface_scroll_handles_empty_lists_and_boundaries` | 1 | desktop_panel, monkeypatch, panel |
| `test_mac_older_tk_keeps_wheel_and_keyboard_navigation` | 1 | desktop_panel, monkeypatch, panel |
| `test_windows_retains_its_existing_scroll_bindings` | 1 | desktop_panel, monkeypatch, panel |
| `test_component_cards_are_twenty_five_percent_shorter` | 2 | monkeypatch, panel, width |
| `test_metadata_group_and_pi_section_spacing` | 3 | compact, gap, height, monkeypatch, panel |
| `test_info_tmcc_id_is_read_only_aligned_and_follows_edited_route` | 6 | existing, height, monkeypatch, panel, system, width |
| `test_compact_info_keeps_two_rows` | 1 | monkeypatch, panel |
| `test_header_and_single_line_selection_follow_card_order` | 1 | monkeypatch, panel |
| `test_touch_card_browsing_hint` | 1 | monkeypatch, panel |
| `test_desktop_card_browsing_hint` | 2 | desktop_panel, monkeypatch, panel |
| `test_search_field_reclaims_label_space_and_uses_search_commit_label` | 3 | compact, height, monkeypatch, panel, width |
| `test_route_builder_buttons_have_shading_relief_and_surrounding_space` | 6 | compact, extra, height, monkeypatch, pad_x, pad_y, panel, spare, system, width |
| `test_pi_buttons_resize_stably_and_shrink_when_space_is_reduced` | 1 | monkeypatch, panel, pi_panel |
| `test_pi_button_resize_ignores_unavailable_editor_geometry` | 4 | monkeypatch, panel, pi_panel, unavailable |
| `test_pi_button_resize_is_scheduled_once_and_retained_in_picker` | 1 | monkeypatch, panel, pi_panel |
| `test_switch_radios_use_large_indicators_and_keep_exclusive_draft_selection` | 1 | monkeypatch, panel |
| `test_picker_indicators_are_large_circles_not_font_glyphs` | 1 | monkeypatch, panel |
| `test_picker_backgrounds_match_catalog_state_and_preserve_selection` | 4 | filter_name, monkeypatch, panel, selected |
| `test_long_card_names_fit_without_changing_the_full_selection_label` | 1 | monkeypatch, panel |
| `test_add_edit_and_remove_only_change_the_draft` | 1 | monkeypatch, panel |
| `test_empty_provisional_route_can_be_opened_without_display_fallback_metadata` | 1 | monkeypatch, panel |
| `test_database_clear_is_a_three_second_hold_only_footer_button` | 1 | monkeypatch, panel |
| `test_clear_deletes_only_the_edited_route_from_base3_and_discards_draft` | 2 | flags, monkeypatch, panel |
| `test_successful_clear_hides_panel_through_popup_manager` | 1 | monkeypatch, panel |
| `test_clear_rechecks_route_availability_at_hold_completion` | 3 | monkeypatch, panel, unavailable |
| `test_clear_is_disabled_while_choosing_a_component` | 1 | monkeypatch, panel |
| `test_failed_clear_keeps_unsaved_route_open` | 2 | failure, monkeypatch, panel |
| `test_closing_or_reconfiguring_cancels_a_pending_clear_hold` | 1 | monkeypatch, panel |
| `test_editing_switch_position_preserves_other_flag_bits` | 1 | monkeypatch, panel |
| `test_nested_route_add_is_draft_only_and_has_no_switch_controls` | 1 | monkeypatch, panel |
| `test_recursive_routes_are_blocked_with_an_explanation` | 2 | indirect, monkeypatch, panel |
| `test_unloaded_nested_route_is_not_added` | 1 | monkeypatch, panel |
| `test_navigation_reaches_all_sixteen_without_reordering` | 1 | monkeypatch, panel |
| `test_move_keeps_selection_on_same_component_and_does_not_sort` | 1 | monkeypatch, panel |
| `test_clear_all_requires_confirmation_and_preserves_metadata` | 1 | monkeypatch, panel |
| `test_add_to_route_requires_a_current_selection` | 2 | filter_name, monkeypatch, panel |
| `test_picker_scope_order_and_show_unlabeled_checkbox` | 1 | monkeypatch, panel |
| `test_picker_filters_switches_by_is_user_defined_not_display_labels` | 6 | labeled, monkeypatch, panel, user_defined |
| `test_show_unlabeled_never_includes_deleted_or_out_of_range_switches` | 2 | monkeypatch, panel, show_unlabeled |
| `test_show_unlabeled_clears_hidden_selection_and_cursor_and_preserves_draft` | 1 | monkeypatch, panel |
| `test_show_unlabeled_preserves_filter_sort_search_and_is_ignored_for_routes` | 1 | monkeypatch, panel |
| `test_picker_filter_sort_search_and_choices_are_remembered` | 1 | monkeypatch, panel |
| `test_search_button_clears_text_and_restores_filtered_sorted_list` | 12 | filter_name, monkeypatch, panel, search, show_unlabeled |
| `test_search_can_still_be_edited_by_selecting_text_and_cleared_during_edit` | 1 | monkeypatch, panel |
| `test_clearing_search_in_editor_restores_edit_button_without_changing_metadata_buttons` | 1 | monkeypatch, panel |
| `test_picker_selection_distinguishes_route_and_switch_with_same_id` | 1 | monkeypatch, panel |
| `test_picker_rechecks_deleted_components_before_adding` | 1 | monkeypatch, panel |
| `test_picker_arrows_and_tap_use_scrolled_coordinates` | 1 | monkeypatch, panel |
| `test_swiping_cards_does_not_select_or_reorder_and_tap_does` | 1 | monkeypatch, panel |
| `test_cancel_protects_components_metadata_and_pending_keyboard_edits` | 1 | monkeypatch, panel |
| `test_touch_cancel_uses_large_pane_centered_confirmation` | 6 | compact, height, monkeypatch, panel, result, width |
| `test_desktop_cancel_uses_new_wording_in_native_dialog` | 2 | desktop_panel, monkeypatch, panel |
| `test_discard_dialog_has_large_message_and_buttons_with_safe_default` | 1 | monkeypatch |
| `test_discard_dialog_return_only_discards_when_explicitly_focused` | 2 | discard_focused |
| `test_picker_cancel_does_not_discard_route_or_prompt_for_search` | 1 | monkeypatch, panel |
| `test_unchanged_route_can_close_without_prompt` | 1 | monkeypatch, panel |
| `test_invalid_metadata_is_visible_and_prevents_save` | 1 | monkeypatch, panel |
| `test_existing_metadata_edits_are_isolated_and_reopening_discards_them` | 1 | monkeypatch, panel |
| `test_save_new_route_creates_provisional_target_only_on_save` | 1 | monkeypatch, panel |
| `test_failed_save_keeps_unsaved_draft_open` | 1 | monkeypatch, panel |
| `test_save_submits_metadata_and_ordered_components_without_operating_layout` | 1 | monkeypatch, panel |
| `test_builder_uses_entered_id_not_previous_ops_selection_and_does_not_create_record` | 1 | monkeypatch |
| `test_builder_opens_existing_route_from_ops_and_preserves_out_variant` | 4 | flags, monkeypatch, panel |
| `test_builder_rejects_invalid_new_route_ids` | 4 | tmcc_id |
| `test_declining_discard_prevents_scope_navigation` | 1 |  |

## tests/gui/test_route_draft.py

85 cases; 33 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestRouteDraft::test_invalid_route_ids` | 7 | tmcc_id |
| `TestRouteDraft::test_route_id_boundaries` | 2 | tmcc_id |
| `TestRouteDraft::test_draft_copies_input_and_component_snapshots` | 1 |  |
| `TestRouteDraft::test_edit_remove_sort_and_dirty_tracking` | 1 |  |
| `TestRouteDraft::test_limit_allows_replacement_and_removal_but_not_append` | 1 |  |
| `TestRouteDraft::test_invalid_index_does_not_modify_draft` | 5 | index |
| `TestRouteDraft::test_invalid_component_does_not_modify_draft` | 7 | flags, tmcc_id |
| `TestRouteDraft::test_stored_out_flags_survive_load_reselect_reorder_and_save` | 4 | flags |
| `TestRouteDraft::test_nested_route_with_stored_out_variant_can_be_validated_and_saved` | 1 |  |
| `TestRouteDraft::test_switch_ids_do_not_require_lookup` | 1 |  |
| `TestRouteDraft::test_self_reference_is_rejected_without_lookup` | 1 |  |
| `TestRouteDraft::test_indirect_and_existing_nested_cycles_are_rejected` | 2 | back_reference |
| `TestRouteDraft::test_unverifiable_referenced_routes_are_rejected` | 4 | missing |
| `TestRouteDraft::test_shared_subroutes_and_loaded_empty_route_are_valid` | 1 |  |
| `TestRouteDraft::test_missing_deep_reference_is_rejected` | 1 |  |
| `TestRouteDraft::test_build_request_revalidates_graph_after_edit` | 1 |  |
| `TestRouteDraft::test_build_request_preserves_live_state_metadata_and_flags_without_sending` | 1 |  |
| `TestRouteDraft::test_cleared_request_and_uninitialized_target` | 1 |  |
| `TestRouteDraft::test_build_request_rejects_wrong_target` | 3 | state |
| `TestRouteDraft::test_saved_request_works_with_existing_refresh_contract` | 1 |  |
| `TestRouteDraft::test_append_edit_and_move_keep_sequence_and_selected_index` | 1 |  |
| `TestRouteDraft::test_move_boundaries_and_clear_preserve_metadata` | 1 |  |
| `TestRouteDraft::test_invalid_move_delta_is_atomic` | 4 | delta |
| `TestRouteDraft::test_switch_mode_edit_preserves_all_other_flag_bits` | 6 | flags, mode |
| `TestRouteDraft::test_metadata_and_components_share_dirty_baseline` | 1 |  |
| `TestRouteDraft::test_invalid_metadata_is_atomic` | 12 | road_name, road_number |
| `TestRouteDraft::test_unified_save_uses_metadata_apis_without_sending_or_live_mutation` | 1 |  |
| `TestRouteDraft::test_unified_save_works_with_existing_refresh_contract` | 1 |  |
| `TestRouteDraft::test_empty_route_saves_with_provisional_or_unloaded_state` | 6 | expected, initialized, road_number |
| `TestRouteDraft::test_unified_save_graph_and_encoding_errors_leave_live_state_unchanged` | 1 |  |
| `TestRouteDraft::test_unified_save_rejects_wrong_target` | 3 | state |
| `TestRouteDraft::test_deleted_target_rejects_both_save_apis` | 1 |  |
| `TestRouteDraft::test_cancel_by_discarding_draft_leaves_live_metadata_and_components_unchanged` | 1 |  |

## tests/gui/test_routes_gui.py

29 cases; 16 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_front_page_lists_routes_by_id_and_excludes_deleted_and_empty_records` | 1 | host, monkeypatch, panel |
| `test_refresh_preserves_selection_and_scroll_after_routes_are_added_or_renamed` | 1 | host, monkeypatch, panel |
| `test_sync_gates_both_creation_and_editing_until_queued_notification` | 1 | host, monkeypatch, panel |
| `test_create_rejects_invalid_ids_without_mutating_store` | 8 | host, monkeypatch, panel, value |
| `test_create_opens_draft_and_cancel_returns_to_front_without_creating_record` | 2 | host, monkeypatch, panel, tmcc_id |
| `test_new_route_rejects_an_existing_id_even_if_it_arrived_after_opening_form` | 1 | host, monkeypatch, panel |
| `test_edit_loads_existing_metadata_and_components_without_mutating_live_route` | 1 | host, monkeypatch, panel |
| `test_edit_revalidates_selection_after_route_is_deleted` | 1 | host, monkeypatch, panel |
| `test_window_close_respects_dirty_draft_confirmation` | 2 | allow, host, monkeypatch, panel |
| `test_save_new_route_uses_existing_write_path_and_returns_to_list` | 1 | host, monkeypatch, panel |
| `test_clear_uses_database_clear_and_returns_to_list` | 1 | host, monkeypatch, panel |
| `test_front_page_desktop_bindings_and_real_editor_gestures` | 3 | host, monkeypatch, panel, system |
| `test_double_click_opens_clicked_scrolled_row_but_not_blank_space` | 3 | expected, host, monkeypatch, panel, y |
| `test_scroll_does_not_select_or_open_a_route` | 1 | host, monkeypatch, panel |
| `test_run_window_owns_main_thread_and_sync_start_never_starts_thread` | 1 | host, monkeypatch, panel |
| `test_shutdown_before_sync_stops_watcher` | 1 | host, monkeypatch, panel |

## tests/gui/test_scroll_box.py

61 cases; 45 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_a_window_with_room_for_its_whole_page_hides_nothing` | 1 | _no_display, monkeypatch |
| `test_a_window_given_less_room_than_its_page_holds_the_rest_back` | 1 | _no_display, monkeypatch |
| `test_a_page_that_has_not_been_measured_is_left_at_its_own_height` | 1 | _no_display, monkeypatch |
| `test_the_content_is_placed_across_the_windows_real_width_and_moved_to_scroll` | 1 | _no_display, monkeypatch |
| `test_scrolling_stops_at_the_top_and_at_the_end_of_what_is_hidden` | 1 | _no_display, monkeypatch |
| `test_a_page_that_shrinks_under_a_scroll_pulls_the_window_back_down` | 1 | _no_display, monkeypatch |
| `test_a_page_turn_starts_at_the_top` | 1 | _no_display, monkeypatch |
| `test_a_row_below_the_fold_is_brought_just_into_view` | 1 | _no_display, monkeypatch |
| `test_a_row_above_the_window_is_scrolled_back_up_to` | 1 | _no_display, monkeypatch |
| `test_a_row_already_in_view_moves_nothing` | 1 | _no_display, monkeypatch |
| `test_a_page_that_fits_moves_for_nothing` | 1 | _no_display, monkeypatch |
| `test_a_row_is_taken_as_the_widget_or_as_the_tk_inside_it` | 1 | _no_display, monkeypatch |
| `test_one_notch_of_the_wheel_moves_the_page_one_step_that_way` | 6 | _no_display, event, monkeypatch, notches, sequence |
| `test_surface_scroll_moves_page_by_vertical_pixels_only` | 6 | _no_display, dx, dy, monkeypatch |
| `test_surface_scroll_clamps_at_both_ends_and_ignores_short_pages` | 1 | _no_display, monkeypatch |
| `test_old_tk_fallback_keeps_small_mac_wheel_motion` | 1 | _no_display, monkeypatch |
| `test_a_press_that_barely_moves_is_left_to_whatever_is_under_it` | 1 | _no_display, monkeypatch |
| `test_a_drag_past_the_slop_carries_the_page_with_the_finger` | 1 | _no_display, monkeypatch |
| `test_every_widget_in_the_content_is_tagged_and_tagged_once` | 1 | _no_display, monkeypatch |
| `test_a_widget_built_after_the_page_was_bound_is_picked_up_on_the_next_call` | 1 | _no_display, monkeypatch |
| `test_the_bar_is_drawn_only_while_part_of_the_page_is_out_of_sight` | 1 | _no_display, monkeypatch |
| `test_the_bar_is_placed_down_the_windows_right_hand_edge` | 1 | _no_display, monkeypatch |
| `test_the_bar_is_drawn_in_the_colors_the_catalogs_own_list_is` | 1 | _no_display, monkeypatch |
| `test_the_bar_is_told_what_share_of_the_page_is_showing_and_where_in_it` | 1 | _no_display, monkeypatch |
| `test_the_bar_is_drawn_at_the_width_the_caller_asked_for` | 1 | _no_display, monkeypatch |
| `test_a_window_that_asks_for_no_width_gets_one_the_bar_can_be_worked_at` | 2 | _no_display, asked, monkeypatch |
| `test_a_page_being_held_back_is_drawn_clear_of_the_bar` | 1 | _no_display, monkeypatch |
| `test_a_page_with_room_for_itself_is_drawn_to_the_whole_of_the_window` | 1 | _no_display, monkeypatch |
| `test_the_room_the_bar_took_is_handed_back_when_the_page_comes_to_fit` | 1 | _no_display, monkeypatch |
| `test_a_fit_that_leaves_the_gutter_where_it_was_does_not_place_the_page_again` | 1 | _no_display, monkeypatch |
| `test_the_line_across_the_foot_is_drawn_only_while_a_page_is_held_back` | 1 | _no_display, monkeypatch |
| `test_the_line_is_drawn_across_the_whole_foot_of_the_window_with_the_bar_over_it` | 1 | _no_display, monkeypatch |
| `test_the_line_is_a_gray_hairline_and_nothing_besides` | 1 | _no_display, monkeypatch |
| `test_the_bar_is_worked_by_dragging_it_pressing_it_and_pressing_its_arrows` | 6 | _no_display, asked, monkeypatch, moved |
| `test_a_unit_of_the_bar_and_a_notch_of_the_wheel_are_the_same_step` | 1 | _no_display, monkeypatch |
| `test_a_bar_asked_for_something_it_cannot_be_asked_for_moves_nothing` | 1 | _no_display, monkeypatch |
| `test_a_page_that_is_being_held_back_shows_once_that_it_moves` | 1 | _no_display, monkeypatch |
| `test_a_page_is_shown_that_it_moves_once_and_not_again` | 1 | _no_display, monkeypatch |
| `test_a_page_turn_is_a_new_page_to_be_shown` | 1 | _no_display, monkeypatch |
| `test_a_page_that_fits_and_a_page_already_scrolled_are_shown_nothing` | 1 | _no_display, monkeypatch |
| `test_a_page_with_barely_anything_hidden_is_moved_only_as_far_as_there_is` | 1 | _no_display, monkeypatch |
| `test_a_page_whose_popup_went_down_mid_hint_is_not_put_back_anywhere` | 1 | _no_display, monkeypatch |
| `test_a_page_that_cannot_be_animated_is_not_left_where_the_hint_put_it` | 1 | _no_display, monkeypatch |
| `test_the_window_is_refitted_when_the_content_or_anything_around_it_is_laid_out` | 1 | _no_display, monkeypatch |
| `test_two_changes_before_tk_settles_ask_for_one_refit` | 1 | _no_display, monkeypatch |

## tests/gui/test_scroll_input.py

28 cases; 5 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_precise_delta_decodes_both_axes` | 10 | dx, dy, signed |
| `test_missing_or_invalid_delta_is_ignored` | 4 | event |
| `test_wheel_notches_remain_proportional` | 12 | delta, monkeypatch, platform |
| `test_small_mac_wheel_deltas_are_not_lost` | 1 | monkeypatch |
| `test_sub_row_motion_accumulates_and_resets_on_reversal_or_idle` | 1 | monkeypatch |

## tests/gui/test_scrolling_text.py

7 cases; 7 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_value_returns_base_text_while_label_is_scrolling` | 1 |  |
| `test_auto_manage_retries_when_width_is_not_ready` | 1 |  |
| `test_auto_manage_retries_when_widget_is_not_mapped_yet` | 1 |  |
| `test_map_event_rechecks_scroll_need` | 1 |  |
| `test_auto_manage_schedules_one_start_when_text_needs_scroll` | 1 |  |
| `test_setting_same_logical_value_does_not_cancel_pending_scroll_start` | 1 |  |
| `test_needs_scroll_uses_parent_width_when_label_reports_natural_width` | 1 |  |

## tests/gui/test_state_info_overlay.py

11 cases; 11 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_popup_close_cancels_active_inline_edits_and_delegates` | 1 | monkeypatch |
| `test_update_enables_clear_button_for_deletable_state` | 1 |  |
| `test_update_disables_clear_button_for_non_deletable_state` | 1 |  |
| `test_clear_record_cancels_button_closes_overlay_and_delegates` | 1 |  |
| `test_the_panel_leaves_its_own_footer_whitespace_to_the_popup` | 1 | monkeypatch |
| `test_an_editable_field_is_told_its_own_name` | 1 | monkeypatch |
| `test_an_editable_field_is_told_whether_it_is_on_a_compact_pane` | 1 | monkeypatch |
| `test_a_host_that_never_heard_of_compact_is_treated_as_portrait` | 1 | monkeypatch |
| `test_committing_a_road_name_promotes_the_record` | 1 | monkeypatch |
| `test_committing_a_road_number_promotes_the_record` | 1 | monkeypatch |
| `test_an_unchanged_field_neither_dispatches_nor_promotes` | 1 | monkeypatch |

## tests/gui/test_steam_deck_gui.py

36 cases; 30 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_landscape_defaults_target_native_steam_deck_size` | 1 | monkeypatch |
| `test_build_creates_two_independent_compact_controllers` | 1 | monkeypatch |
| `test_focus_changes_without_altering_other_controller` | 1 |  |
| `test_toggle_focus_alternates_between_panels` | 1 |  |
| `test_focus_arrow_points_toward_active_pane` | 1 |  |
| `test_focus_arrow_is_a_pixel_sized_canvas_bounded_by_header` | 5 | header_height, monkeypatch |
| `test_focus_arrow_has_bounded_fallback_without_header_geometry` | 2 | header_available |
| `test_focus_arrow_remeasures_header_when_repositioned` | 1 |  |
| `test_global_halt_sends_immediately_once` | 1 | monkeypatch |
| `test_destroy_gui_tears_down_both_children` | 1 |  |
| `test_controller_poll_routes_actions_on_tk_thread_and_reschedules` | 1 | monkeypatch |
| `test_controller_shutdown_cancels_poll_and_clears_input` | 1 |  |
| `test_missing_pygame_keeps_touch_gui_available` | 1 | monkeypatch |
| `test_controller_input_tells_the_provider_which_panel_acts_on_the_squeeze` | 1 | monkeypatch |
| `test_panel_replacement_uses_shared_pycab_confirmation` | 2 | result |
| `test_linked_car_transfer_uses_other_panel_and_confirms_occupied_target` | 1 |  |
| `test_linked_car_transfer_handles_empty_target_and_missing_car` | 1 |  |
| `test_controls_overlay_spans_every_column_of_the_body` | 1 | monkeypatch |
| `test_controls_overlay_is_built_once_and_reshown` | 1 | monkeypatch |
| `test_close_controls_reports_whether_it_was_open` | 1 | monkeypatch |
| `test_paging_only_works_while_the_screen_is_up` | 1 | monkeypatch |
| `test_close_sits_in_the_title_band_not_below_the_content` | 1 | monkeypatch |
| `test_the_help_columns_are_budgeted_the_room_under_the_title_band` | 1 | monkeypatch |
| `test_the_help_columns_are_budgeted_the_width_of_the_display` | 1 | monkeypatch |
| `test_controls_panel_is_not_an_overlay_panel` | 1 |  |
| `test_the_help_screen_is_prewarmed_hidden_and_the_press_reuses_it` | 1 | monkeypatch |
| `test_a_press_before_the_prewarm_runs_still_builds_one_screen` | 1 | monkeypatch |
| `test_a_prewarm_during_shutdown_builds_nothing` | 1 | monkeypatch |
| `test_a_prewarm_that_fails_leaves_the_screen_to_the_press` | 1 | monkeypatch |
| `test_showing_and_hiding_re_tucks_the_focus_arrow` | 1 | monkeypatch |

## tests/gui/test_swipe_detector.py

25 cases; 19 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_widget_with_guizero_hooks_uses_them` | 1 | mac_platform, monkeypatch |
| `test_container_without_hooks_falls_back_to_tk_bind` | 1 | mac_platform, monkeypatch |
| `test_swipe_direction_dispatches_on_either_binding_path` | 2 | mac_platform, monkeypatch, widget_factory |
| `test_swipe_ending_outside_the_widget_still_registers` | 2 | mac_platform, monkeypatch, widget_factory |
| `test_swipe_rejected_when_too_short` | 1 | mac_platform, monkeypatch |
| `test_swipe_rejected_when_too_slow` | 1 | mac_platform, monkeypatch |
| `test_swipe_rejected_when_mostly_vertical` | 1 | mac_platform, monkeypatch |
| `test_event_screen_y_reads_both_event_shapes` | 1 | mac_platform, monkeypatch |
| `test_event_targets_covers_guizero_and_tk_widgets` | 1 | mac_platform, monkeypatch |
| `test_bind_directly_avoids_guizero_hooks_and_preserves_bindings` | 1 | mac_platform, monkeypatch |
| `test_should_start_predicate_ignores_gestures_outside_the_region` | 1 | mac_platform, monkeypatch |
| `test_surface_motion_navigates_once_per_burst` | 4 | direction, dx, dy, mac_platform, monkeypatch |
| `test_surface_reversal_and_region_rejection_reset_gesture` | 1 | mac_platform, monkeypatch |
| `test_surface_input_cancels_press_without_long_press_or_release_navigation` | 1 | mac_platform, monkeypatch |
| `test_swipe_old_tk_fallback_preserves_bindings` | 1 | mac_platform, monkeypatch |
| `test_non_mac_swipe_bindings_unchanged` | 2 | mac_platform, monkeypatch, platform |
| `test_swipe_surface_handles_destroyed_widget` | 1 | mac_platform, monkeypatch |
| `test_should_start_rejection_does_not_leave_a_stale_press` | 1 | mac_platform, monkeypatch |
| `test_long_press_suppresses_the_swipe` | 1 | mac_platform, monkeypatch |

## tests/gui/test_touch_list.py

9 cases; 4 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_surface_binds_locally_to_canvas_and_every_row` | 1 | monkeypatch, touch_list |
| `test_precise_pixels_and_axis_filter` | 6 | dx, dy, monkeypatch, touch_list |
| `test_surface_clamps_and_empty_list_does_not_scroll` | 1 | monkeypatch, touch_list |
| `test_older_tk_preserves_local_wheel_support` | 1 | monkeypatch, touch_list |

## tests/gui/test_touch_list_box.py

19 cases; 16 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_precise_scrolling_accumulates_small_deltas_without_selecting` | 2 | controller, mod, monkeypatch |
| `test_precise_horizontal_scroll_obeys_policy` | 2 | horizontal, mod, monkeypatch |
| `test_precise_scroll_clamps_and_discards_outward_remainder` | 1 | mod, monkeypatch |
| `test_empty_disabled_and_destroyed_list_ignores_scroll` | 1 | mod, monkeypatch |
| `test_old_tk_retains_small_mac_wheel_events` | 1 | mod, monkeypatch |
| `test_non_mac_list_keeps_native_wheel_bindings` | 2 | mod, monkeypatch, platform |
| `test_init_disables_horizontal_scroll_by_default` | 1 | mod, monkeypatch |
| `test_set_horizontal_scroll_false_realigns_scrolled_list` | 1 | mod, monkeypatch |
| `test_set_item_style_applies_per_row_colors` | 1 | mod, monkeypatch |
| `test_set_item_style_with_none_styles_last_row` | 1 | mod, monkeypatch |
| `test_set_item_style_ignores_empty_style` | 1 | mod, monkeypatch |
| `test_release_realigns_list_when_horizontal_scroll_is_disabled` | 1 | mod, monkeypatch |
| `test_activate_highlighted_fires_hold_select_for_selected_row` | 1 | mod, monkeypatch |
| `test_activate_highlighted_falls_back_to_active_row` | 1 | mod, monkeypatch |
| `test_move_highlight_shifts_selection_and_scrolls_into_view` | 1 | mod, monkeypatch |
| `test_move_highlight_clamps_at_ends_without_wrapping` | 1 | mod, monkeypatch |

## tests/gui/test_touch_scrollbar.py

2 cases; 1 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_touch_scrollbar_keeps_native_behavior_and_sets_minimum_image_size` | 2 | length, monkeypatch, width |

## tests/gui/test_wide_component_state_gui.py

6 cases; 6 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_direct_single_gui_per_pane_builds_without_combo` | 1 | _patch_classes, monkeypatch |
| `test_multi_gui_set_creates_expected_panes` | 1 | _patch_classes, monkeypatch |
| `test_invalid_gui_name_raises_value_error` | 1 | _patch_classes, monkeypatch |
| `test_operating_accessories_screen_is_accepted` | 1 | _patch_classes, monkeypatch |
| `test_wide_gui_accepts_basic_dimensions` | 1 | _patch_classes, monkeypatch |
| `test_operating_accessories_renders_image_and_mounts_controls` | 1 | _patch_classes, monkeypatch |

## tests/integration/test_pytrain_api_exit.py

34 cases; 3 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_api_exit_receiver` | 24 | action, role, route |
| `test_api_callback_cache_failure` | 2 | role |
| `test_api_real_signal_handoff` | 8 | action, role, route |

## tests/pdi/test_amc2_req.py

8 cases; 8 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_parse_config_rx_from_bytes_minimal_fields_present` | 1 | mock_pdi_dispatcher_ip |
| `test_get_motor_and_lamp_bounds_safe` | 1 | mock_pdi_dispatcher_ip |
| `test_direction_and_output_type_labels_and_flags` | 1 | mock_pdi_dispatcher_ip |
| `test_motor_action_payload_and_as_bytes_structure` | 1 | mock_pdi_dispatcher_ip |
| `test_lamp_action_payload_and_as_bytes_structure` | 1 | mock_pdi_dispatcher_ip |
| `test_motor_config_set_serialization_and_payload_defaults` | 1 | mock_pdi_dispatcher_ip |
| `test_update_config_applies_motor_and_lamp_changes` | 1 | mock_pdi_dispatcher_ip |
| `test_as_bytes_get_requests_have_minimal_payload_for_motor_and_lamp` | 1 | mock_pdi_dispatcher_ip |

## tests/pdi/test_asc2_req.py

10 cases; 10 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_config_set_as_bytes_contains_fields_and_delay_scaled` | 1 | mock_pdi_dispatcher_ip |
| `test_control1_set_payload_and_time_byte` | 1 | mock_pdi_dispatcher_ip |
| `test_control2_set_values_valids_current_behavior` | 1 | mock_pdi_dispatcher_ip |
| `test_control3_rx_payload_relays_and_valids` | 1 | mock_pdi_dispatcher_ip |
| `test_control3_set_as_bytes_sub_id_and_time_byte_current_behavior_and_payload` | 1 | mock_pdi_dispatcher_ip |
| `test_control4_set_payload_thru_and_time_byte_and_is_thru` | 1 | mock_pdi_dispatcher_ip |
| `test_control4_rx_payload_thru_or_out` | 1 | mock_pdi_dispatcher_ip |
| `test_control5_set_payload_thru_and_value_byte_and_is_thru` | 1 | mock_pdi_dispatcher_ip |
| `test_identify_set_includes_ident_byte` | 1 | mock_pdi_dispatcher_ip |
| `test_get_requests_have_minimal_payload_for_config` | 1 | mock_pdi_dispatcher_ip |

## tests/pdi/test_base3_buffer.py

6 cases; 6 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_singleton_lifecycle_and_accessors` | 1 | clean_singletons, mock_pdi_dispatcher_ip, monkeypatch |
| `test_enqueue_command_sends_bytes_and_keepalive_triggers` | 1 | clean_singletons, controlled_keepalive, mock_pdi_dispatcher_ip, monkeypatch, reset_singletons |
| `test_multibyte_tmcc_command_is_packetized_and_sync_state_called` | 1 | clean_singletons, mock_pdi_dispatcher_ip, monkeypatch, reset_singletons |
| `test_request_state_update_enqueues_when_valid_id_and_scope` | 1 | clean_singletons, mock_pdi_dispatcher_ip, monkeypatch |
| `test_sync_state_parses_tmcc_stream_and_may_emit_update_requests` | 1 | clean_singletons, mock_pdi_dispatcher_ip, monkeypatch, reset_singletons |
| `test_keepalive_thread_sends_every_two_seconds` | 1 | clean_singletons, controlled_keepalive, mock_pdi_dispatcher_ip, monkeypatch |

## tests/pdi/test_base_req.py

427 cases; 30 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_incoming_speed_packet_matches_fixed_wire_examples` | 4 | address_bytes, command, expected, mock_pdi_dispatcher_ip |
| `test_incoming_speed_echo_preserves_stuffed_checksum` | 2 | command, expected_payload, mock_pdi_dispatcher_ip, monkeypatch, packet, scope, speed_update_lookups, target_speed |
| `test_incoming_speed_update_carries_target` | 36 | address, address_bytes, command, label, mock_pdi_dispatcher_ip, monkeypatch, scope, speed_update_lookups, target_speed |
| `test_incoming_speed_update_without_record_lookup_result` | 6 | command, label, mock_pdi_dispatcher_ip, monkeypatch, scope, speed_update_lookups, target_speed |
| `test_short_speed_send_and_marked_echo` | 2 | command, echo_packet, mock_pdi_dispatcher_ip, monkeypatch, scope, sent_packet, speed_update_lookups |
| `test_process_sync_reqs_preserves_mixed_dispatch_order` | 2 | do_async, mock_pdi_dispatcher_ip, monkeypatch, sync_dispatch |
| `test_process_sync_reqs_empty_input` | 2 | do_async, mock_pdi_dispatcher_ip, monkeypatch, sync_dispatch |
| `test_absolute_speed_updates_follow_ramp_lifecycle` | 8 | data_bytes, initialized_update_state, legacy_packets, legacy_speed, mock_pdi_dispatcher_ip, monkeypatch, native_speed_state, outbound_speed_lookups, sync_dispatch, tmcc_packets, tmcc_speed |
| `test_updates_to_reqs_converts_native_target_to_engine_speed_scale` | 12 | data_bytes, initialized_update_state, legacy_packets, legacy_speed, mock_pdi_dispatcher_ip, monkeypatch, native_speed_state, outbound_speed_lookups, sync_dispatch, tmcc_packets, tmcc_speed |
| `test_updates_to_reqs_preserves_requests_and_refresh_marker` | 12 | address, initialized_update_state, mock_pdi_dispatcher_ip, monkeypatch, refresh, sync_dispatch |
| `test_initialized_update_paths_preserve_mixed_results` | 12 | address, entry_point, initialized_update_state, mock_pdi_dispatcher_ip, monkeypatch, sync_dispatch |
| `test_encode_decode_labor_rpm_roundtrip` | 1 | mock_pdi_dispatcher_ip |
| `test_encode_throw_rate_defaults_and_mapped_values` | 9 | expected, mock_pdi_dispatcher_ip, rate |
| `test_parsed_numeric_conversions` | 14 | brake, command, expected_brake, expected_momentum, mock_pdi_dispatcher_ip, momentum |
| `test_parsed_fuel_and_water_display` | 8 | command, level, mock_pdi_dispatcher_ip, percentage |
| `test_base_memory_minimal_as_bytes_structure` | 1 | mock_pdi_dispatcher_ip |
| `test_outbound_speed_update_rejects_missing_d4_mapping` | 8 | address, mock_pdi_dispatcher_ip, monkeypatch, outbound_speed_lookups, scope, state |
| `test_outbound_speed_packet_matches_fixed_wire_examples` | 10 | address, address_bytes, command, engine_packet, engine_target, label, mock_pdi_dispatcher_ip, monkeypatch, outbound_speed_lookups, scope, train_packet |
| `test_outbound_speed_update_carries_target` | 72 | address, address_bytes, command, label, mock_pdi_dispatcher_ip, monkeypatch, outbound_speed_lookups, scope, target_speed, use_factory |
| `test_outbound_speed_factory_defaults_to_engine` | 18 | address, address_bytes, mock_pdi_dispatcher_ip, monkeypatch, outbound_speed_lookups, target_speed |
| `test_update_speed_engine_and_train_encode_distinct` | 2 | address, engine_packet, mock_pdi_dispatcher_ip, monkeypatch, outbound_speed_lookups, train_packet |
| `test_properties_defaults_and_payload_safe_strings` | 1 | mock_pdi_dispatcher_ip |
| `test_set_valid_preserves_masks_and_is_idempotent` | 70 | already_set, field, mock_pdi_dispatcher_ip, valid1, valid2 |
| `test_clear_valid_preserves_masks_and_is_idempotent` | 70 | already_set, field, mock_pdi_dispatcher_ip, valid1, valid2 |
| `test_set_then_clear_valid_restores_unrelated_masks` | 35 | field, mock_pdi_dispatcher_ip, valid1, valid2 |
| `test_is_valid_low_field_with_empty_low_word_and_populated_high_word` | 6 | field, mock_pdi_dispatcher_ip, valid1 |
| `test_is_active_logic_for_empty_records_engine_like_fields` | 1 | mock_pdi_dispatcher_ip |
| `test_a_populated_base_memory_record_does_not_report_itself_empty` | 1 | mock_pdi_dispatcher_ip |
| `test_a_never_written_base_memory_record_reports_itself_empty` | 1 | mock_pdi_dispatcher_ip |
| `test_as_key_tuple_shape_and_content_stability` | 1 | mock_pdi_dispatcher_ip |

## tests/pdi/test_bpc2_req.py

7 cases; 7 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_config_set_as_bytes_contains_fields_and_restore_bit` | 1 | mock_pdi_dispatcher_ip |
| `test_control1_set_payload_and_state_byte` | 1 | mock_pdi_dispatcher_ip |
| `test_control3_set_payload_off` | 1 | mock_pdi_dispatcher_ip |
| `test_control2_set_values_valids_current_behavior` | 1 | mock_pdi_dispatcher_ip |
| `test_control4_set_values_valids_current_behavior` | 1 | mock_pdi_dispatcher_ip |
| `test_identify_set_includes_ident_byte` | 1 | mock_pdi_dispatcher_ip |
| `test_get_requests_have_minimal_payload` | 1 | mock_pdi_dispatcher_ip |

## tests/pdi/test_constants.py

16 cases; 9 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_pdi_command_basic_classification_flags` | 1 | mock_pdi_dispatcher_ip |
| `test_pdi_command_collections_suffix_sets_are_consistent` | 1 | mock_pdi_dispatcher_ip |
| `test_pdi_action_common_properties_and_bytes` | 1 | mock_pdi_dispatcher_ip |
| `test_common_action_is_config_detection` | 1 | mock_pdi_dispatcher_ip |
| `test_d4_action_capabilities_matrix` | 1 | mock_pdi_dispatcher_ip |
| `test_pdi_action_repr_has_option_flags` | 8 | enum_cls, mock_pdi_dispatcher_ip |
| `test_action_bytes_do_not_collide_within_each_enum` | 1 | mock_pdi_dispatcher_ip |
| `test_pdi_command_sendable_receivable_logic_spotchecks` | 1 | mock_pdi_dispatcher_ip |
| `test_as_bytes_single_byte_roundtrip_subset` | 1 | mock_pdi_dispatcher_ip |

## tests/pdi/test_d4_req.py

7 cases; 7 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_lionel_timestamp_bytes_length_and_endianness` | 1 | mock_pdi_dispatcher_ip, monkeypatch |
| `test_build_count_request_roundtrip_engine` | 1 | mock_pdi_dispatcher_ip |
| `test_build_first_rec_request_roundtrip_train` | 1 | mock_pdi_dispatcher_ip |
| `test_build_map_request_roundtrip_with_tmcc_id` | 1 | mock_pdi_dispatcher_ip |
| `test_build_query_request_with_data_bytes_and_auto_timestamp_roundtrip` | 1 | mock_pdi_dispatcher_ip, monkeypatch |
| `test_timestamp_str_empty_when_none` | 1 | mock_pdi_dispatcher_ip |
| `test_as_key_structure_and_stability` | 1 | mock_pdi_dispatcher_ip |

## tests/pdi/test_irda_req.py

142 cases; 26 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_config_rx_as_bytes_contains_fields` | 1 | mock_pdi_dispatcher_ip |
| `test_sequence_set_includes_sequence_byte` | 1 | mock_pdi_dispatcher_ip |
| `test_identify_set_includes_ident_byte` | 1 | mock_pdi_dispatcher_ip |
| `test_get_requests_have_minimal_payload_for_config` | 1 | mock_pdi_dispatcher_ip |
| `test_data_resolves_default_engine_by_big_endian_bluetooth_id` | 8 | bluetooth_id, engine_id, expected_id, mock_pdi_dispatcher_ip, monkeypatch, resolved_id, state_lookups |
| `test_data_bluetooth_lookup_miss_preserves_engine_id` | 2 | engine_id, mock_pdi_dispatcher_ip, monkeypatch, state_lookups |
| `test_data_nondefault_engine_does_not_use_bluetooth_lookup` | 4 | engine_id, mock_pdi_dispatcher_ip, monkeypatch, state_lookups |
| `test_data_validates_train_without_creating_state` | 3 | exists, expected, mock_pdi_dispatcher_ip, monkeypatch, state_lookups, train_id |
| `test_data_decodes_fields_and_payload` | 3 | direction, left_to_right, mock_pdi_dispatcher_ip, monkeypatch, right_to_left, state_lookups |
| `test_data_truncated_valid_packets_default_missing_fields` | 28 | length, mock_pdi_dispatcher_ip, monkeypatch, state_lookups |
| `test_minimal_data_payload_omits_missing_fields` | 1 | mock_pdi_dispatcher_ip, monkeypatch, state_lookups |
| `test_config_decodes_available_fields` | 8 | length, mock_pdi_dispatcher_ip |
| `test_config_payload_engine_filters` | 3 | expected_lr, expected_rl, loco_lr, loco_rl, mock_pdi_dispatcher_ip |
| `test_sequence_decode_and_integer_construction` | 10 | mock_pdi_dispatcher_ip, sequence |
| `test_empty_action_payload_defaults` | 2 | action, mock_pdi_dispatcher_ip |
| `test_record_status_map` | 6 | code, expected, mock_pdi_dispatcher_ip |
| `test_product_revision_map` | 3 | code, expected, mock_pdi_dispatcher_ip, monkeypatch, state_lookups |
| `test_product_id_map` | 16 | code, expected, mock_pdi_dispatcher_ip, monkeypatch, state_lookups |
| `test_tsdb_map` | 18 | code, expected, mock_pdi_dispatcher_ip |
| `test_outgoing_defaults_and_scope` | 3 | expected, mock_pdi_dispatcher_ip, scope |
| `test_get_serialization_is_exactly_header_only` | 4 | action, mock_pdi_dispatcher_ip |
| `test_identify_serialization_defaults_and_stuffing` | 6 | ident, mock_pdi_dispatcher_ip |
| `test_config_rx_serialization_round_trip` | 4 | debug, mock_pdi_dispatcher_ip |
| `test_serialization_falls_back_without_action_body` | 4 | action, command, mock_pdi_dispatcher_ip |
| `test_info_decodes_inherited_fields_and_forces_irda_scope` | 1 | mock_pdi_dispatcher_ip |
| `test_error_payload_uses_inherited_representation` | 1 | mock_pdi_dispatcher_ip |

## tests/pdi/test_lcs_req.py

12 cases; 12 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_is_lcs_true_and_repr_safe_without_payload` | 1 | mock_pdi_dispatcher_ip |
| `test_parse_status_from_bytes_populates_fields_and_payload_text` | 1 | mock_pdi_dispatcher_ip |
| `test_parse_firmware_payload_text` | 1 | mock_pdi_dispatcher_ip |
| `test_parse_info_payload_text` | 1 | mock_pdi_dispatcher_ip |
| `test_error_flag_sets_is_error_and_maps_error_code_text` | 1 | mock_pdi_dispatcher_ip |
| `test_error_code_unknown_maps_to_none_text` | 1 | mock_pdi_dispatcher_ip |
| `test_error_code_error_texts` | 1 | mock_pdi_dispatcher_ip |
| `test_uart_mode_mapping_and_base_type_defaults_to_na` | 1 | mock_pdi_dispatcher_ip |
| `test_identify_set_payload_includes_ident_when_command_is_set` | 1 | mock_pdi_dispatcher_ip |
| `test_payload_falls_back_when_not_matching_any_clause` | 1 | mock_pdi_dispatcher_ip |
| `test_ser2req_from_bytes_sets_action_enum` | 1 | mock_pdi_dispatcher_ip |
| `test_is_action_helper_against_lists` | 1 | mock_pdi_dispatcher_ip |

## tests/pdi/test_pdi_listener.py

6 cases; 6 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_build_and_singleton` | 1 | clean_singletons, mock_pdi_dispatcher_ip |
| `test_listen_for_raises_when_not_built` | 1 | clean_singletons, mock_pdi_dispatcher_ip |
| `test_offer_parses_and_publishes_broadcast` | 1 | clean_singletons, mock_pdi_dispatcher_ip |
| `test_scope_subscription_receives_expected_message` | 1 | clean_singletons, mock_pdi_dispatcher_ip |
| `test_dispatcher_offer_accepts_bytes_or_req_and_filters_ack_ping_free_path` | 1 | clean_singletons, mock_pdi_dispatcher_ip |
| `test_dispatcher_publishes_delete_for_inactive_base_memory_record` | 1 | clean_singletons, mock_pdi_dispatcher_ip, monkeypatch |

## tests/pdi/test_pdi_req.py

14 cases; 11 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_encode_decode_text_roundtrip_ascii_and_nulls` | 1 | mock_pdi_dispatcher_ip |
| `test_encode_text_exact_bytes` | 4 | expected, mock_pdi_dispatcher_ip, text |
| `test_decode_text_stops_at_null_and_skips_ffs` | 1 | mock_pdi_dispatcher_ip |
| `test_decode_int_valid_and_invalid` | 1 | mock_pdi_dispatcher_ip |
| `test_decode_int_all_ffs_returns_zero` | 1 | mock_pdi_dispatcher_ip |
| `test_decode_int_none_raises_type_error` | 1 | mock_pdi_dispatcher_ip |
| `test_scope_record_length_map` | 1 | mock_pdi_dispatcher_ip |
| `test_ping_req_as_bytes_framing_and_checksum` | 1 | mock_pdi_dispatcher_ip |
| `test_tmcc_as_packets_three_byte_tmcc2_command` | 1 | mock_pdi_dispatcher_ip |
| `test_tmcc_as_packets_four_digit_tmcc4_command` | 1 | mock_pdi_dispatcher_ip |
| `test_calculate_checksum_adds_stuff_bytes_for_reserved_values` | 1 | mock_pdi_dispatcher_ip |

## tests/pdi/test_pdi_state_store.py

4 cases; 4 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_singleton_returns_same_instance` | 1 | mock_pdi_dispatcher_ip, reset_singleton |
| `test_singleton_thread_safety` | 1 | mock_pdi_dispatcher_ip, reset_singleton |
| `test_init_only_called_once` | 1 | mock_pdi_dispatcher_ip, monkeypatch, reset_singleton |
| `test_register_pdi_device_delegates_and_returns` | 1 | mock_pdi_dispatcher_ip, monkeypatch, reset_singleton |

## tests/pdi/test_stm2_req.py

6 cases; 6 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_config_set_as_bytes_contains_fields` | 1 | mock_pdi_dispatcher_ip |
| `test_control1_set_payload_and_state_byte_out` | 1 | mock_pdi_dispatcher_ip |
| `test_control1_set_payload_and_state_byte_thru` | 1 | mock_pdi_dispatcher_ip |
| `test_identify_set_includes_ident_byte` | 1 | mock_pdi_dispatcher_ip |
| `test_get_requests_have_minimal_payload_for_config` | 1 | mock_pdi_dispatcher_ip |
| `test_is_thru_is_out_properties_match_state` | 1 | mock_pdi_dispatcher_ip |

## tests/protocol/multibyte/test_ramp_command_req.py

429 cases; 48 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_ramp_repr` | 8 | command, from_tmcc_rx, scope |
| `test_ramp_timestamp_roundtrip` | 6 | command, timestamp_ms |
| `test_ramp_roundtrip` | 24 | address, command, from_tmcc_rx, scope |
| `test_build_dispatch` | 8 | builder, command |
| `test_ramp_builder_decodes_wire_payload` | 24 | address, builder, command, scope |
| `test_ramp_builder_rejects_noncanonical_wire_address` | 16 | address_bytes, builder, command |
| `test_ramp_builder_rejects_incomplete_wire_payload` | 10 | builder, payload |
| `test_ramp_instance_send_entry_points_rejected` | 16 | address, command, entry_point, parsed, scope |
| `test_ramp_class_send_entry_points_rejected` | 16 | builder, command, entry_point |
| `test_ramp_encoded_send_entry_points_rejected` | 4 | command, entry_point |
| `test_ramp_private_enqueue_rejected` | 4 | as_request, command |
| `test_normal_variable_send_entry_points_unchanged` | 4 | entry_point |
| `test_build_defaults_and_payload_copy` | 2 | payload_type |
| `test_claim_wire_encoding` | 1 |  |
| `test_serialization_does_not_mutate_request` | 6 | address, scope |
| `test_updated_logical_address_and_scope` | 6 | address, scope |
| `test_endpoint_and_claim_id_form_identity` | 1 |  |
| `test_valid_endpoints` | 10 | claim_id, host, port |
| `test_invalid_payload` | 10 | payload |
| `test_invalid_unicast_endpoint` | 6 | host |
| `test_invalid_host` | 7 | host |
| `test_invalid_endpoint_integer` | 14 | field, value |
| `test_invalid_timestamp` | 18 | command, timestamp_ms |
| `test_timestamp_is_required_keyword` | 2 | command |
| `test_zero_timestamp_in_payload` | 10 | builder, command |
| `test_zero_endpoint_integer_in_payload` | 2 | offset |
| `test_invalid_scope` | 4 | scope |
| `test_invalid_address` | 8 | address |
| `test_ramp_rejects_other_commands` | 2 | command |
| `test_variable_parser_delegates_address_values_to_builder` | 8 | address, is_d4, scope |
| `test_variable_parser_delegates_unsupported_address_encoding` | 4 | address, scope |
| `test_variable_address_decoder_rejects_incomplete_four_digit_address` | 4 | digit_count |
| `test_variable_parser_preserves_original_framing_checks` | 8 | mutation, scope |
| `test_malformed_packets` | 40 | address, mutation, scope |
| `test_malformed_four_digit_address` | 10 | scope, suffix |
| `test_framed_wrong_payload_length` | 20 | address, size |
| `test_invalid_logical_address_header` | 8 | address, scope |
| `test_logical_address_header_checksum` | 2 | offset |
| `test_noncanonical_framing_address` | 6 | address, scope |
| `test_truncated_packets` | 2 | address |
| `test_shared_variable_command_family` | 1 |  |
| `test_variable_target_speed_roundtrip` | 18 | address, builder, scope |
| `test_variable_target_speed_payload` | 3 | payload |
| `test_variable_target_speed_rejects_invalid_speed` | 6 | payload |
| `test_variable_target_speed_rejects_invalid_packets` | 4 | mutation |
| `test_variable_parser_preserves_payload_without_range_validation` | 1 |  |
| `test_parameter_builder_rejects_variable_definitions` | 15 | command |
| `test_existing_variable_commands` | 20 | address, command, data, scope |

## tests/protocol/multibyte/test_ramp_listener.py

36 cases; 1 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_listener_consumes_ramp_followed_by_speed` | 36 | address, command, scope, timestamp_ms |

## tests/protocol/sequence/test_ramp_peer.py

47 cases; 22 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_first_claim_needs_only_normal_broadcast_and_no_sockets` | 1 | monkeypatch, pdi_send, peers, ramp_target_update |
| `test_known_owner_rejects_new_ramp_without_contacting_or_canceling_it` | 1 | pdi_send, peers, ramp_target_update |
| `test_simultaneous_claims_accept_first_in_broadcast_order` | 2 | monkeypatch, pdi_send, peers, ramp_target_update, reverse |
| `test_second_local_claim_cannot_bypass_pending_first_claim` | 1 | pdi_send, peers, ramp_target_update |
| `test_cancellation_during_claim_wait_never_succeeds` | 1 | pdi_send, peers, ramp_target_update |
| `test_missing_own_announcement_fails_closed` | 1 | pdi_send, peers, ramp_target_update |
| `test_release_is_nonblocking_and_claim_refresh_is_not_a_handoff` | 1 | monkeypatch, pdi_send, peers, ramp_target_update |
| `test_publication_failure_releases_candidate_without_fallback` | 1 | pdi_send, peers, ramp_target_update |
| `test_claim_publication_uses_existing_state_api_only` | 1 | monkeypatch, pdi_send, ramp_target_update |
| `test_client_source_address_is_used_without_discovery` | 1 | monkeypatch, pdi_send, ramp_target_update |
| `test_manual_address_override_requires_no_transport` | 1 | monkeypatch, pdi_send, ramp_target_update |
| `test_server_state_publication_never_enters_hardware_buffers` | 1 | monkeypatch, pdi_send, ramp_target_update |
| `test_client_state_publication_wraps_claim_in_existing_state_request` | 1 | pdi_send, ramp_target_update |
| `test_real_owner_keeps_destination_and_competitor_emits_nothing` | 4 | address, engine_states, monkeypatch, pdi_send, peers, ramp_target_update, scope |
| `test_startup_target_follows_claim_and_precedes_every_component` | 6 | first_command, pdi_send, ramp_target_update, scope, speed, target |
| `test_failed_or_canceled_acquisition_never_announces_target` | 2 | canceled, pdi_send, ramp_target_update |
| `test_target_send_failure_releases_claim_without_component_commands` | 1 | pdi_send, ramp_target_update |
| `test_database_update_failure_releases_claim_without_component_commands` | 1 | pdi_send, ramp_target_update |
| `test_real_ramp_emits_only_after_claim_confirmation_and_releases_on_completion` | 1 | engine_states, monkeypatch, pdi_send, peers, ramp_target_update |
| `test_timestamp_race_converges_without_startup_echo` | 16 | address, engine_states, monkeypatch, pdi_send, peers, ramp_target_update, reverse, same_millisecond, scope |
| `test_unconfirmed_claim_refreshes_locally_and_keeps_original_timestamp` | 1 | engine_states, monkeypatch, pdi_send, peers, ramp_target_update |
| `test_own_echo_does_not_cancel_or_rebase_local_destination` | 1 | engine_states, monkeypatch, pdi_send, peers, ramp_target_update |

## tests/protocol/sequence/test_ramp_registry.py

15 cases; 15 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestRampRegistry::test_build_returns_one_registry` | 1 | _xunit_setup_method_fixture_TestRampRegistry, pdi_send |
| `TestRampRegistry::test_reset_drops_the_singleton` | 1 | _xunit_setup_method_fixture_TestRampRegistry, pdi_send |
| `TestRampRegistry::test_engine_and_train_with_the_same_id_are_distinct_targets` | 1 | _xunit_setup_method_fixture_TestRampRegistry, pdi_send |
| `TestRampRegistry::test_distinct_targets_ramp_concurrently_without_cross_talk` | 1 | _xunit_setup_method_fixture_TestRampRegistry, pdi_send |
| `TestRampRegistry::test_second_ramp_to_retargets_the_running_thread` | 1 | _xunit_setup_method_fixture_TestRampRegistry, pdi_send |
| `TestRampRegistry::test_burst_of_requests_yields_one_thread_and_nine_retargets` | 1 | _xunit_setup_method_fixture_TestRampRegistry, pdi_send |
| `TestRampRegistry::test_ramp_to_carries_the_dialog_flag_through_a_retarget` | 1 | _xunit_setup_method_fixture_TestRampRegistry, pdi_send |
| `TestRampRegistry::test_every_ramp_thread_is_a_daemon` | 1 | _xunit_setup_method_fixture_TestRampRegistry, pdi_send |
| `TestRampRegistry::test_settled_ramps_are_reaped` | 1 | _xunit_setup_method_fixture_TestRampRegistry, pdi_send |
| `TestRampRegistry::test_a_reaped_target_gets_a_new_thread` | 1 | _xunit_setup_method_fixture_TestRampRegistry, pdi_send |
| `TestRampRegistry::test_abort_stops_and_forgets_one_ramp` | 1 | _xunit_setup_method_fixture_TestRampRegistry, pdi_send |
| `TestRampRegistry::test_abort_of_an_unknown_target_is_harmless` | 1 | _xunit_setup_method_fixture_TestRampRegistry, pdi_send |
| `TestRampRegistry::test_abort_all_by_scope_leaves_the_other_scope_alone` | 1 | _xunit_setup_method_fixture_TestRampRegistry, pdi_send |
| `TestRampRegistry::test_abort_all_stops_every_scope` | 1 | _xunit_setup_method_fixture_TestRampRegistry, pdi_send |
| `TestEngineStateRoutesThroughTheRegistry::test_state_ramp_to_registers_and_mirrors_the_handle` | 1 | _xunit_setup_method_fixture_TestEngineStateRoutesThroughTheRegistry, pdi_send |

## tests/protocol/sequence/test_ramp_residuals.py

32 cases; 20 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_claim_is_public_and_initialized_before_acquisition` | 1 | pdi_send |
| `test_start_returns_before_claim_acknowledgment_without_emitting` | 1 | pdi_send |
| `test_race_rejection_aborts_worker_without_speed_or_component_transmissions` | 1 | caplog, pdi_send |
| `test_pending_claim_ignores_ordinary_reports_without_replaying_them` | 1 | pdi_send |
| `test_every_direction_overrides_pending_claim_and_repeat_suppression` | 2 | pdi_send, protocol |
| `test_numeric_safety_overrides_pending_claim_on_every_repeat` | 4 | data, pdi_send, protocol |
| `test_named_safety_aliases_override_pending_claim_on_every_repeat` | 2 | pdi_send, protocol |
| `test_remote_registry_guard_precedes_retarget_and_construction` | 1 | monkeypatch, pdi_send |
| `test_mock_remote_flag_does_not_reject_local_retarget` | 1 | pdi_send |
| `test_registry_retargets_pending_worker_without_reacquiring_or_blocking` | 1 | pdi_send |
| `test_safety_abort_while_acquiring_stops_without_waiting_or_late_speeds` | 1 | pdi_send |
| `test_ordinary_takeover_is_completely_silent` | 1 | pdi_send |
| `test_zero_is_foreign_even_when_it_was_sent` | 2 | is_rx, pdi_send |
| `test_ordinary_abort_during_send_prevents_trailing_components` | 1 | pdi_send |
| `test_peer_release_preserves_replacement_flags_and_database_target` | 1 | pdi_send |
| `test_peer_acquisition_precedes_emission_and_always_releases` | 4 | error, pdi_send |
| `test_default_peer_setup_is_lazy_and_fails_closed` | 4 | error, monkeypatch, pdi_send |
| `test_peer_release_error_cannot_leave_running_flags_set` | 1 | caplog, pdi_send |
| `test_completed_claim_releases_without_linger_and_only_once` | 1 | monkeypatch, pdi_send |
| `test_retarget_during_settle_keeps_claim_and_restores_ramping_flag` | 1 | monkeypatch, pdi_send |

## tests/protocol/sequence/test_ramp_speed_req.py

68 cases; 25 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestRampSpeedReq::test_repr` | 8 | _xunit_setup_method_fixture_TestRampSpeedReq, cls, monkeypatch, pdi_send, scope, speed |
| `TestRampSpeedReq::test_new_sequence_enums_exist` | 1 | _xunit_setup_method_fixture_TestRampSpeedReq, pdi_send |
| `TestRampSpeedReq::test_new_sequence_enums_do_not_collide` | 1 | _xunit_setup_method_fixture_TestRampSpeedReq, pdi_send |
| `TestRampSpeedReq::test_command_classes_are_registered` | 1 | _xunit_setup_method_fixture_TestRampSpeedReq, pdi_send |
| `TestRampSpeedReq::test_sequence_req_build_dispatches_to_the_facade` | 2 | _xunit_setup_method_fixture_TestRampSpeedReq, cls, command, monkeypatch, pdi_send |
| `TestRampSpeedReq::test_ramp_destination_stays_local` | 12 | _xunit_setup_method_fixture_TestRampSpeedReq, as_action, is_legacy, monkeypatch, pdi_send, scope, send_request, speed |
| `TestRampSpeedReq::test_tmcc1_target_speed_is_sanitized_to_31` | 1 | _xunit_setup_method_fixture_TestRampSpeedReq, monkeypatch, pdi_send |
| `TestRampSpeedReq::test_train_scope_is_carried_through` | 1 | _xunit_setup_method_fixture_TestRampSpeedReq, monkeypatch, pdi_send |
| `TestRampSpeedReq::test_no_step_expansion` | 1 | _xunit_setup_method_fixture_TestRampSpeedReq, monkeypatch, pdi_send |
| `TestRampSpeedReq::test_dialog_variant_adds_tower_and_engineer` | 1 | _xunit_setup_method_fixture_TestRampSpeedReq, monkeypatch, pdi_send |
| `TestRampSpeedReq::test_dialog_variant_on_tmcc1` | 1 | _xunit_setup_method_fixture_TestRampSpeedReq, monkeypatch, pdi_send |
| `TestRampSpeedReq::test_rr_speed_string_resolves_to_a_speed` | 1 | _xunit_setup_method_fixture_TestRampSpeedReq, monkeypatch, pdi_send |
| `TestRampSpeedReq::test_on_before_send_hands_the_target_to_the_state` | 1 | _xunit_setup_method_fixture_TestRampSpeedReq, monkeypatch, pdi_send |
| `TestRampSpeedReq::test_dialog_variant_passes_the_dialog_flag` | 1 | _xunit_setup_method_fixture_TestRampSpeedReq, monkeypatch, pdi_send |
| `TestRampSpeedReq::test_ramp_starts_before_any_bytes_go_out` | 1 | _xunit_setup_method_fixture_TestRampSpeedReq, monkeypatch, pdi_send |
| `TestRampSpeedReq::test_no_state_falls_back_to_absolute_speed` | 1 | _xunit_setup_method_fixture_TestRampSpeedReq, monkeypatch, pdi_send |
| `TestRampSpeedReq::test_state_without_a_speed_falls_back` | 1 | _xunit_setup_method_fixture_TestRampSpeedReq, monkeypatch, pdi_send |
| `TestRampSpeedReq::test_default_address_emits_both_generations_plus_rpm` | 1 | _xunit_setup_method_fixture_TestRampSpeedReq, monkeypatch, pdi_send |
| `TestRampSpeedReq::test_fallback_sends_without_starting_a_ramp` | 1 | _xunit_setup_method_fixture_TestRampSpeedReq, monkeypatch, pdi_send |
| `TestRampSpeedReq::test_base_is_not_registered` | 1 | _xunit_setup_method_fixture_TestRampSpeedReq, pdi_send |
| `TestRampSpeedReq::test_ramped_speed_req_is_still_registered` | 1 | _xunit_setup_method_fixture_TestRampSpeedReq, pdi_send |
| `TestRampSpeedReq::test_rejected_owner_emits_no_components_or_dialog` | 8 | _xunit_setup_method_fixture_TestRampSpeedReq, as_action, monkeypatch, pdi_send, request_type |
| `TestRampSpeedReq::test_scheduled_ramp_keeps_real_steps_without_target_announcements` | 16 | _xunit_setup_method_fixture_TestRampSpeedReq, current, destination, is_legacy, monkeypatch, pdi_send, scope, send_request |
| `TestRampSpeedReq::test_unknown_speed_fallback_cannot_override_a_remote_owner` | 2 | _xunit_setup_method_fixture_TestRampSpeedReq, monkeypatch, pdi_send, request_type |
| `TestRampSpeedReq::test_immediate_speed_cancels_ramps_without_writing_a_destination` | 2 | _xunit_setup_method_fixture_TestRampSpeedReq, is_legacy, monkeypatch, pdi_send |

## tests/protocol/sequence/test_speed_ramp.py

84 cases; 61 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestSpeedRamp::test_initial_target_uses_scope_address_and_base_speed_scale` | 20 | _xunit_setup_method_fixture_TestSpeedRamp, address, encoded, is_legacy, pdi_send, ramp_target_update, scope, target |
| `TestSpeedRamp::test_initial_target_uses_the_live_ceiling` | 2 | _xunit_setup_method_fixture_TestSpeedRamp, ceiling, encoded, is_legacy, pdi_send, ramp_target_update, target |
| `TestSpeedRamp::test_initial_target_requires_active_ownership` | 2 | _xunit_setup_method_fixture_TestSpeedRamp, acquired, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_initial_target_checks_cancellation_after_entering_the_send_gate` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, monkeypatch, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_thread_is_a_named_daemon` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_thread_runs_and_exits_on_its_own` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_run_owns_the_ramping_flag_until_completion` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_run_sends_a_step_before_its_first_pause` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, monkeypatch, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_a_sender_exception_releases_local_ramp_ownership` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_ramp_up_is_monotonic_and_lands_exactly` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_ramp_down_is_monotonic_and_drops_rpm_and_effort_up_front` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_retarget_changes_only_the_local_request` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_retarget_up_to_up_continues_from_the_commanded_speed` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_retarget_up_to_down_reverses_from_the_commanded_speed` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_retarget_does_not_resample_the_effort_baseline` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_abort_mid_ramp_drives_the_engine_no_further` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_abort_before_the_first_step` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_abort_leaves_the_reached_speed_as_the_target` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_abort_with_an_explicit_target_records_it` | 2 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update, target |
| `TestSpeedRamp::test_a_second_abort_does_not_rewrite_the_target` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_a_hard_stop_returns_effort_to_neutral` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_an_ordinary_abort_hands_the_operators_effort_back` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_an_abort_hands_back_an_effort_setting_changed_mid_ramp` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_a_ramp_that_never_raised_effort_hands_nothing_back` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_a_tmcc1_hard_stop_sends_no_effort_command` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_a_takeover_our_step_overtook_is_re_asserted` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_a_takeover_nothing_overtook_is_not_re_asserted` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_nothing_is_re_asserted_before_the_first_step` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_a_hard_stop_yields_nothing` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_a_hard_stop_re_asserts_the_standstill_a_step_overtook` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_a_hard_stop_re_asserts_nothing_when_every_step_is_echoed` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_a_tmcc1_hard_stop_re_asserts_the_standstill_without_effort` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_an_abort_waits_for_a_step_already_on_the_wire` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, monkeypatch, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_an_abort_stalled_on_the_wire_still_completes` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, monkeypatch, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_an_abort_during_deceleration_priming_silences_the_rpm_drop` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_a_settle_after_an_abort_lands_nothing` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_a_stopped_ramp_sends_nothing_but_the_aborts_own_commands` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_momentum_raised_mid_ramp_changes_the_next_increment` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_speed_limit_lowered_mid_ramp_caps_the_ramp` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_speed_limit_raised_or_cleared_mid_ramp_resumes_the_original_target` | 2 | _xunit_setup_method_fixture_TestSpeedRamp, cleared, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_speed_limit_below_the_commanded_speed_reverses_the_ramp` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_max_speed_and_speed_limit_together_take_the_lower` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_settle_sends_the_target_once_with_biased_rpm_and_restored_effort` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_target_equals_current_speed_sends_one_absolute_speed` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_effort_follows_the_shared_curve_and_only_on_change` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_rpm_is_emitted_only_on_change` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_scaled_engine_reaches_the_top_notch_at_its_own_ceiling` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_speed_limit_does_not_move_the_notches` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_bias_on_a_scaled_curve_is_preserved` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_max_speed_changed_mid_ramp_switches_maps_and_rederives_the_bias` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_a_trim_applied_at_rest_survives_the_whole_ramp` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_a_trim_carries_into_the_up_front_deceleration_drop` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_no_redundant_opening_rpm` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_a_trim_at_the_ceiling_pins_every_notch` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_a_trim_at_rest_on_a_scaled_map` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_a_trim_survives_a_burst_of_retargets` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_a_foreign_rpm_overrides_a_trim_derived_at_rest` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_tmcc1_ramps_by_one_and_emits_no_rpm_or_effort` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_tmcc1_max_speed_never_reaches_the_rpm_map` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_non_rpm_engine_emits_effort_but_no_rpm` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |
| `TestSpeedRamp::test_linger_absorbs_a_retarget_into_the_same_thread` | 1 | _xunit_setup_method_fixture_TestSpeedRamp, pdi_send, ramp_target_update |

## tests/protocol/sequence/test_speed_ramp_echoes.py

71 cases; 43 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestEchoLedger::test_a_recorded_value_is_claimed` | 1 | _xunit_setup_method_fixture_TestEchoLedger, pdi_send |
| `TestEchoLedger::test_an_unrecorded_value_is_not_claimed` | 1 | _xunit_setup_method_fixture_TestEchoLedger, pdi_send |
| `TestEchoLedger::test_a_none_value_is_never_recorded_or_claimed` | 1 | _xunit_setup_method_fixture_TestEchoLedger, pdi_send |
| `TestEchoLedger::test_a_step_echo_out_of_sequence_is_not_ours` | 1 | _xunit_setup_method_fixture_TestEchoLedger, pdi_send |
| `TestEchoLedger::test_step_echoes_are_claimed_strictly_in_send_order` | 1 | _xunit_setup_method_fixture_TestEchoLedger, pdi_send |
| `TestEchoLedger::test_delayed_speed_reports_can_skip_steps_but_not_go_backward` | 2 | _xunit_setup_method_fixture_TestEchoLedger, monkeypatch, pdi_send, speeds |
| `TestEchoLedger::test_speed_reports_follow_send_order_across_a_reversal` | 1 | _xunit_setup_method_fixture_TestEchoLedger, pdi_send |
| `TestEchoLedger::test_sound_and_effort_still_require_the_next_pending_echo` | 2 | _xunit_setup_method_fixture_TestEchoLedger, family, pdi_send |
| `TestEchoLedger::test_only_the_value_just_matched_is_still_claimable` | 1 | _xunit_setup_method_fixture_TestEchoLedger, pdi_send |
| `TestEchoLedger::test_the_value_just_matched_expires_with_the_lag_budget` | 1 | _xunit_setup_method_fixture_TestEchoLedger, pdi_send |
| `TestEchoLedger::test_echoes_arriving_in_order_are_claimed_one_at_a_time` | 1 | _xunit_setup_method_fixture_TestEchoLedger, pdi_send |
| `TestEchoLedger::test_re_echo_of_a_claimed_value_is_accepted_without_consuming` | 1 | _xunit_setup_method_fixture_TestEchoLedger, pdi_send |
| `TestEchoLedger::test_the_documented_ser2_replay_cannot_reach_a_ledger` | 1 | _xunit_setup_method_fixture_TestEchoLedger, pdi_send |
| `TestEchoLedger::test_families_are_independent` | 1 | _xunit_setup_method_fixture_TestEchoLedger, pdi_send |
| `TestEchoLedger::test_tolerance_matches_a_value_shifted_by_one` | 1 | _xunit_setup_method_fixture_TestEchoLedger, pdi_send |
| `TestEchoLedger::test_tolerance_applies_to_the_claimed_ring_too` | 1 | _xunit_setup_method_fixture_TestEchoLedger, pdi_send |
| `TestEchoLedger::test_an_echo_arriving_past_the_ttl_is_a_deviation` | 1 | _xunit_setup_method_fixture_TestEchoLedger, pdi_send |
| `TestEchoLedger::test_purge_drops_stale_pending_and_claimed_entries` | 1 | _xunit_setup_method_fixture_TestEchoLedger, pdi_send |
| `TestEchoLedger::test_an_echo_inside_the_ttl_survives_a_purge` | 1 | _xunit_setup_method_fixture_TestEchoLedger, monkeypatch, pdi_send |
| `TestEchoLedger::test_echoes_expire_at_the_configured_ttl` | 4 | _xunit_setup_method_fixture_TestEchoLedger, age, claimed, monkeypatch, pdi_send |
| `TestEchoLedger::test_the_claimed_ring_is_bounded` | 1 | _xunit_setup_method_fixture_TestEchoLedger, pdi_send |
| `TestEchoLedger::test_pending_echo_carries_its_timestamp` | 1 | _xunit_setup_method_fixture_TestEchoLedger, pdi_send |
| `TestEchoFamily::test_commands_map_to_their_family` | 7 | _xunit_setup_method_fixture_TestEchoFamily, command, family, pdi_send |
| `TestEchoFamily::test_an_unarbitrated_command_has_no_family` | 1 | _xunit_setup_method_fixture_TestEchoFamily, pdi_send |
| `TestRampArbitration::test_feedback_streams_advance_independently` | 12 | _xunit_setup_method_fixture_TestRampArbitration, command, leading_rx, monkeypatch, pdi_send, values |
| `TestRampArbitration::test_each_feedback_stream_still_rejects_foreign_speeds` | 6 | _xunit_setup_method_fixture_TestRampArbitration, foreign, is_rx, monkeypatch, pdi_send |
| `TestRampArbitration::test_local_retargets_neither_send_commands_nor_change_echo_history` | 1 | _xunit_setup_method_fixture_TestRampArbitration, pdi_send |
| `TestRampArbitration::test_a_retarget_mid_flight_does_not_orphan_the_step_in_flight` | 1 | _xunit_setup_method_fixture_TestRampArbitration, pdi_send |
| `TestRampArbitration::test_every_step_the_ramp_sent_is_claimed` | 1 | _xunit_setup_method_fixture_TestRampArbitration, pdi_send |
| `TestRampArbitration::test_an_accounted_for_step_leaves_the_queue` | 1 | _xunit_setup_method_fixture_TestRampArbitration, pdi_send |
| `TestRampArbitration::test_a_speed_the_ramp_swept_through_earlier_is_foreign` | 1 | _xunit_setup_method_fixture_TestRampArbitration, pdi_send |
| `TestRampArbitration::test_a_step_is_recorded_before_it_is_sent` | 1 | _xunit_setup_method_fixture_TestRampArbitration, pdi_send |
| `TestRampArbitration::test_the_reordered_ser2_stream_reads_as_a_takeover` | 1 | _xunit_setup_method_fixture_TestRampArbitration, pdi_send |
| `TestRampArbitration::test_the_commanded_speed_is_always_ours` | 1 | _xunit_setup_method_fixture_TestRampArbitration, pdi_send |
| `TestRampArbitration::test_an_initial_speed_that_was_never_sent_is_foreign` | 1 | _xunit_setup_method_fixture_TestRampArbitration, pdi_send |
| `TestRampArbitration::test_an_echo_past_the_ttl_looks_foreign` | 1 | _xunit_setup_method_fixture_TestRampArbitration, pdi_send |
| `TestRampArbitration::test_tmcc1_claims_an_echo_shifted_by_one` | 1 | _xunit_setup_method_fixture_TestRampArbitration, pdi_send |
| `TestRampArbitration::test_legacy_has_no_speed_tolerance` | 1 | _xunit_setup_method_fixture_TestRampArbitration, pdi_send |
| `TestRampArbitration::test_a_foreign_absolute_speed_is_foreign` | 1 | _xunit_setup_method_fixture_TestRampArbitration, pdi_send |
| `TestRampArbitration::test_retired_targets_do_not_arbitrate_or_change_local_intent` | 2 | _xunit_setup_method_fixture_TestRampArbitration, command, pdi_send |
| `TestRampArbitration::test_a_foreign_rpm_is_absorbed_not_fatal` | 1 | _xunit_setup_method_fixture_TestRampArbitration, pdi_send |
| `TestRampArbitration::test_a_foreign_labor_re_baselines_the_effort_restore` | 1 | _xunit_setup_method_fixture_TestRampArbitration, pdi_send |
| `TestRampArbitration::test_an_unarbitrated_command_leaves_the_ramp_alone` | 1 | _xunit_setup_method_fixture_TestRampArbitration, pdi_send |

## tests/protocol/sequence/test_speed_ramp_geometry.py

523 cases; 60 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestSpeedRampGeometry::test_labor_delta_is_the_shared_curve` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_legacy_increment_by_momentum_band` | 8 | _xunit_setup_method_fixture_TestSpeedRampGeometry, expected, momentum, pdi_send |
| `TestSpeedRampGeometry::test_tmcc1_increment_is_always_one` | 6 | _xunit_setup_method_fixture_TestSpeedRampGeometry, momentum, pdi_send |
| `TestSpeedRampGeometry::test_legacy_increment_with_no_momentum` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_legacy_delay_by_momentum` | 8 | _xunit_setup_method_fixture_TestSpeedRampGeometry, momentum, pdi_send |
| `TestSpeedRampGeometry::test_tmcc1_delay_by_momentum` | 8 | _xunit_setup_method_fixture_TestSpeedRampGeometry, momentum, pdi_send |
| `TestSpeedRampGeometry::test_delay_falls_back_when_momentum_unknown` | 2 | _xunit_setup_method_fixture_TestSpeedRampGeometry, is_legacy, pdi_send |
| `TestSpeedRampGeometry::test_delay_is_monotonic_in_momentum` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_ceiling_neither_limit_legacy` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_ceiling_neither_limit_tmcc1` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_ceiling_speed_limit_only` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_ceiling_max_speed_only` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_ceiling_both_limits_takes_the_lower` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_ceiling_speed_max_none_falls_back_by_generation` | 2 | _xunit_setup_method_fixture_TestSpeedRampGeometry, expected, is_legacy, pdi_send |
| `TestSpeedRampGeometry::test_ceiling_unset_speed_max_falls_back_by_generation` | 2 | _xunit_setup_method_fixture_TestSpeedRampGeometry, expected, is_legacy, pdi_send |
| `TestSpeedRampGeometry::test_effective_target_clamps_to_the_live_ceiling` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_effective_target_below_the_ceiling_is_untouched` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_effective_target_never_negative` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_effective_target_none_requested` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_tmcc1_effective_target_capped_at_31` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_rpm_max_speed_is_none_for_tmcc1` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_rpm_max_speed_is_the_roster_ceiling_for_legacy` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_rpm_max_speed_unknown_uses_base_table` | 3 | _xunit_setup_method_fixture_TestSpeedRampGeometry, max_speed, pdi_send |
| `TestSpeedRampGeometry::test_rpm_max_speed_ignores_speed_limit` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_biased_rpm_zero_bias_is_the_base_table` | 23 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send, speed |
| `TestSpeedRampGeometry::test_biased_rpm_is_table_plus_bias_clamped` | 115 | _xunit_setup_method_fixture_TestSpeedRampGeometry, bias, pdi_send, speed |
| `TestSpeedRampGeometry::test_biased_rpm_on_a_scaled_map` | 66 | _xunit_setup_method_fixture_TestSpeedRampGeometry, bias, pdi_send, speed |
| `TestSpeedRampGeometry::test_biased_rpm_clamped_to_the_notch_range` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_scaled_map_reaches_the_top_notch_where_the_base_does_not` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_bias_zero_for_non_rpm_engine` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_bias_zero_when_speed_unknown` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_bias_at_rest_is_the_reported_rpm` | 8 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send, rpm |
| `TestSpeedRampGeometry::test_bias_zero_at_rest_when_rpm_unknown` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_bias_at_rest_on_a_scaled_map` | 8 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send, rpm |
| `TestSpeedRampGeometry::test_bias_matches_the_documented_example` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_bias_derived_from_the_base_table_and_clamped` | 154 | _xunit_setup_method_fixture_TestSpeedRampGeometry, offset, pdi_send, speed |
| `TestSpeedRampGeometry::test_bias_derived_from_the_engines_own_scaled_map` | 63 | _xunit_setup_method_fixture_TestSpeedRampGeometry, offset, pdi_send, speed |
| `TestSpeedRampGeometry::test_bias_and_emission_use_the_same_map` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_bias_held_to_the_notch_range` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_a_deliberate_trim_is_not_reduced` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_negative_extreme_floors_the_emitted_rpm` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_bias_zero_for_tmcc1` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_next_step_none_at_the_target` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_next_step_none_when_the_ceiling_already_holds_us` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_next_step_accelerates_by_the_increment` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_next_step_does_not_overshoot_the_target` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_next_step_decelerates` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_next_step_does_not_undershoot_the_target` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_next_step_reads_momentum_live` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_next_step_clamps_to_the_live_ceiling` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_a_ceiling_below_the_commanded_speed_reverses_the_ramp` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_next_step_labor_follows_the_shared_curve` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_next_step_rpm_follows_the_table_plus_bias` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_next_step_rpm_follows_the_engines_own_scaled_map` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_a_speed_limit_does_not_move_the_notches` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_next_step_rpm_none_on_deceleration` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_next_step_rpm_none_for_non_rpm_engine` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_next_step_tmcc1_emits_neither_rpm_nor_labor` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_tmcc1_ramp_stays_within_its_own_range` | 1 | _xunit_setup_method_fixture_TestSpeedRampGeometry, pdi_send |
| `TestSpeedRampGeometry::test_legacy_ramp_is_strictly_monotonic_and_lands_on_target` | 3 | _xunit_setup_method_fixture_TestSpeedRampGeometry, momentum, pdi_send |

## tests/protocol/sequence/test_two_controller_ramp.py

19 cases; 13 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestTwoControllerRamp::test_legacy_engine_has_a_populated_record_before_updates` | 2 | _xunit_setup_method_fixture_TestTwoControllerRamp, monkeypatch, one_process, pdi_send, speed |
| `TestTwoControllerRamp::test_the_second_ramp_wins` | 1 | _xunit_setup_method_fixture_TestTwoControllerRamp, monkeypatch, one_process, pdi_send |
| `TestTwoControllerRamp::test_other_nodes_observe_speed_without_owning_the_ramp` | 1 | _xunit_setup_method_fixture_TestTwoControllerRamp, monkeypatch, one_process, pdi_send |
| `TestTwoControllerRamp::test_delayed_echoes_keep_ramping_until_a_backward_or_unsent_speed` | 2 | _xunit_setup_method_fixture_TestTwoControllerRamp, monkeypatch, one_process, pdi_send, takeover_speed |
| `TestTwoControllerRamp::test_server_ramp_survives_a_base_echo_overtaken_by_local_feedback` | 1 | _xunit_setup_method_fixture_TestTwoControllerRamp, monkeypatch, one_process, pdi_send |
| `TestTwoControllerRamp::test_takeover_yields_only_steps_unacknowledged_by_either_stream` | 4 | _xunit_setup_method_fixture_TestTwoControllerRamp, is_rx, monkeypatch, one_process, pdi_send, pending_step |
| `TestTwoControllerRamp::test_the_loser_drives_the_engine_no_further` | 1 | _xunit_setup_method_fixture_TestTwoControllerRamp, monkeypatch, one_process, pdi_send |
| `TestTwoControllerRamp::test_the_loser_hands_back_the_effort_it_borrowed` | 1 | _xunit_setup_method_fixture_TestTwoControllerRamp, monkeypatch, one_process, pdi_send |
| `TestTwoControllerRamp::test_the_first_controller_is_left_clean` | 1 | _xunit_setup_method_fixture_TestTwoControllerRamp, monkeypatch, one_process, pdi_send |
| `TestTwoControllerRamp::test_the_loser_observes_steps_not_the_winners_local_destination` | 1 | _xunit_setup_method_fixture_TestTwoControllerRamp, monkeypatch, one_process, pdi_send |
| `TestTwoControllerRamp::test_only_one_ramp_is_left_on_the_layout` | 1 | _xunit_setup_method_fixture_TestTwoControllerRamp, monkeypatch, one_process, pdi_send |
| `TestTwoControllerRamp::test_a_hard_stop_after_the_handoff_cleans_up_both_controllers` | 1 | _xunit_setup_method_fixture_TestTwoControllerRamp, monkeypatch, one_process, pdi_send |
| `TestTwoControllerRamp::test_competing_claim_cannot_emit_or_cancel_owner_and_can_start_after_release` | 2 | _xunit_setup_method_fixture_TestTwoControllerRamp, monkeypatch, one_process, pdi_send, target |

## tests/protocol/test_command_base.py

1 cases; 1 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestCommandBase::test_can_not_instantiate_command_base` | 1 |  |

## tests/protocol/test_command_req.py

104 cases; 21 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestCommandReq::test_send_command` | 1 | _xunit_setup_method_fixture_TestCommandReq |
| `TestCommandReq::test_retired_target_speed_cannot_reach_the_buffer` | 30 | _xunit_setup_method_fixture_TestCommandReq, address, api, command, scope |
| `TestCommandReq::test_variable_target_speed_data` | 30 | _xunit_setup_method_fixture_TestCommandReq, address, data, scope |
| `TestCommandReq::test_variable_target_speed_invalid_data` | 3 | _xunit_setup_method_fixture_TestCommandReq, data |
| `TestCommandReq::test_state_only_ramp_roundtrip` | 12 | _xunit_setup_method_fixture_TestCommandReq, address, command, scope |
| `TestCommandReq::test_state_only_ramp_cannot_reach_the_buffer` | 12 | _xunit_setup_method_fixture_TestCommandReq, api, command |
| `TestCommandReq::test_synthetic_target_effects_are_not_sent` | 2 | _xunit_setup_method_fixture_TestCommandReq, monkeypatch, target |
| `TestCommandReq::test_determine_first_byte` | 1 | _xunit_setup_method_fixture_TestCommandReq |
| `TestCommandReq::test_vet_request` | 1 | _xunit_setup_method_fixture_TestCommandReq |
| `TestCommandReq::test_enqueue_command` | 1 | _xunit_setup_method_fixture_TestCommandReq |
| `TestCommandReq::test_address` | 1 | _xunit_setup_method_fixture_TestCommandReq |
| `TestCommandReq::test_data` | 1 | _xunit_setup_method_fixture_TestCommandReq |
| `TestCommandReq::test_scope` | 1 | _xunit_setup_method_fixture_TestCommandReq |
| `TestCommandReq::test_command_def` | 1 | _xunit_setup_method_fixture_TestCommandReq |
| `TestCommandReq::test_bits` | 1 | _xunit_setup_method_fixture_TestCommandReq |
| `TestCommandReq::test_num_data_bits` | 1 | _xunit_setup_method_fixture_TestCommandReq |
| `TestCommandReq::test_syntax` | 1 | _xunit_setup_method_fixture_TestCommandReq |
| `TestCommandReq::test_identifier` | 1 | _xunit_setup_method_fixture_TestCommandReq |
| `TestCommandReq::test_build_tmcc1_command_req` | 1 | _xunit_setup_method_fixture_TestCommandReq |
| `TestCommandReq::test_build_tmcc2_command_req` | 1 | _xunit_setup_method_fixture_TestCommandReq |
| `TestCommandReq::test_build_parameter_command_req` | 1 | _xunit_setup_method_fixture_TestCommandReq |

## tests/protocol/test_constants.py

10 cases; 10 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestConstants::test_by_name_mixin` | 1 | _xunit_setup_method_fixture_TestConstants |
| `TestConstants::test_by_name_mixin_in_enums` | 1 | _xunit_setup_method_fixture_TestConstants |
| `TestConstants::test_tmcc1_constants` | 1 | _xunit_setup_method_fixture_TestConstants |
| `TestConstants::test_the_tmcc1_smoke_commands_own_the_numeric_keys_they_alias` | 1 | _xunit_setup_method_fixture_TestConstants |
| `TestConstants::test_tmcc2_constants` | 1 | _xunit_setup_method_fixture_TestConstants |
| `TestConstants::test_to_rr_speed_resolves_the_band_that_contains_the_speed` | 1 | _xunit_setup_method_fixture_TestConstants |
| `TestConstants::test_to_rr_speed_can_still_be_asked_for_the_step_a_band_starts_at` | 1 | _xunit_setup_method_fixture_TestConstants |
| `TestConstants::test_command_scope_enum` | 1 | _xunit_setup_method_fixture_TestConstants |
| `TestConstants::test_engine_option_enum` | 1 | _xunit_setup_method_fixture_TestConstants |
| `TestConstants::test_engine_option` | 1 | _xunit_setup_method_fixture_TestConstants |

## tests/protocol/test_speed_to_rpm.py

88 cases; 15 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestSpeedToRpm::test_bands_recovered_from_base_table` | 1 | _xunit_setup_method_fixture_TestSpeedToRpm |
| `TestSpeedToRpm::test_identity_at_or_above_threshold` | 6 | _xunit_setup_method_fixture_TestSpeedToRpm, max_speed |
| `TestSpeedToRpm::test_default_argument_matches_base_table` | 1 | _xunit_setup_method_fixture_TestSpeedToRpm |
| `TestSpeedToRpm::test_scaled_map_is_distinct_and_cached` | 9 | _xunit_setup_method_fixture_TestSpeedToRpm, max_speed |
| `TestSpeedToRpm::test_scaled_bands_strictly_increasing_and_non_empty` | 9 | _xunit_setup_method_fixture_TestSpeedToRpm, max_speed |
| `TestSpeedToRpm::test_rpm_monotonic_in_speed` | 9 | _xunit_setup_method_fixture_TestSpeedToRpm, max_speed |
| `TestSpeedToRpm::test_notch_zero_at_a_stop` | 9 | _xunit_setup_method_fixture_TestSpeedToRpm, max_speed |
| `TestSpeedToRpm::test_top_notch_reached_at_max_speed` | 9 | _xunit_setup_method_fixture_TestSpeedToRpm, max_speed |
| `TestSpeedToRpm::test_scaled_curve_climbs_faster_than_base_curve` | 1 | _xunit_setup_method_fixture_TestSpeedToRpm |
| `TestSpeedToRpm::test_boundaries_within_one_of_proportional_ideal` | 9 | _xunit_setup_method_fixture_TestSpeedToRpm, max_speed |
| `TestSpeedToRpm::test_full_coverage_no_key_error` | 13 | _xunit_setup_method_fixture_TestSpeedToRpm, max_speed |
| `TestSpeedToRpm::test_speed_above_ceiling_resolves_to_top_notch` | 9 | _xunit_setup_method_fixture_TestSpeedToRpm, max_speed |
| `TestSpeedToRpm::test_absurdly_low_ceiling_still_well_formed` | 1 | _xunit_setup_method_fixture_TestSpeedToRpm |
| `TestSpeedToRpm::test_reset_cache_rebuilds_map` | 1 | _xunit_setup_method_fixture_TestSpeedToRpm |
| `TestSpeedToRpm::test_edited_base_table_reshapes_every_scaled_map` | 1 | _xunit_setup_method_fixture_TestSpeedToRpm, monkeypatch |

## tests/protocol/test_tmcc1_acc_aux_numbers.py

22 cases; 4 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestAccAuxNumbers::test_members_exist` | 10 | digit |
| `TestAccAuxNumbers::test_as_bytes_is_the_numeric` | 10 | digit |
| `TestAccAuxNumbers::test_aux1_prefix_is_generated_at_acc_scope` | 1 | monkeypatch |
| `TestAccAuxNumbers::test_alias_map_untouched` | 1 |  |

## tests/protocol/test_validations.py

1 cases; 1 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestValidations::test_validate_int` | 1 | _xunit_setup_method_fixture_TestValidations |

## tests/test_deck_packaging.py

15 cases; 15 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_pyproject_declares_the_deck_distribution` | 1 | config |
| `test_both_distributions_package_pycab_confirmation_images` | 1 | build_deck, config |
| `test_the_excluded_requirements_are_the_gpio_only_ones` | 1 | config |
| `test_every_excluded_requirement_is_actually_a_dependency` | 1 | config |
| `test_the_deck_build_renames_the_project_and_drops_the_gpio_requirements` | 1 | build_deck, config |
| `test_the_deck_build_leaves_the_pi_packaging_flow_alone` | 1 | build_deck, config |
| `test_the_deck_build_reads_the_version_before_it_rewrites_pyproject` | 1 | build_deck, monkeypatch, sandbox, tmp_path, tmp_path_factory |
| `test_the_build_is_pinned_to_the_version_of_the_clean_tree` | 1 | build_deck, monkeypatch, sandbox, tmp_path, tmp_path_factory |
| `test_a_local_version_is_refused_before_anything_is_built` | 1 | build_deck, monkeypatch, sandbox, tmp_path, tmp_path_factory |
| `test_a_local_version_can_still_be_built_on_request` | 1 | build_deck, monkeypatch, sandbox, tmp_path, tmp_path_factory |
| `test_the_pinned_version_follows_the_projects_setuptools_scm_settings` | 1 | build_deck, config, monkeypatch |
| `test_the_release_workflow_builds_and_publishes_both_distributions` | 1 |  |
| `test_installed_package_recognizes_the_deck_distribution` | 1 | monkeypatch |
| `test_installed_package_recognizes_the_pi_distribution` | 1 | monkeypatch |
| `test_installed_package_reports_a_source_checkout` | 1 | monkeypatch |

## tests/test_pytest.py

3 cases; 3 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestPyTrain::test_get_version` | 1 | _xunit_setup_method_fixture_TestPyTrain |
| `TestPyTrain::test_get_version_strips_package_local_metadata` | 1 | _xunit_setup_method_fixture_TestPyTrain, monkeypatch |
| `TestPyTrain::test_get_version_strips_git_local_metadata` | 1 | _xunit_setup_method_fixture_TestPyTrain, monkeypatch |

## tests/test_update_policy.py

1 cases; 1 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_self_update_disabled` | 1 | monkeypatch |

## tests/test_version_tuple.py

5 cases; 2 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_version_tuple_valid` | 2 | expected, monkeypatch, version |
| `test_version_tuple_rejects_invalid_versions` | 3 | monkeypatch, version |

## tests/utils/test_argument_parser.py

10 cases; 10 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestPyTrainArgumentParser::test_error_raises_without_exit_and_sets_message` | 1 |  |
| `TestPyTrainArgumentParser::test_exit_raises_without_exit_and_sets_message` | 1 |  |
| `TestPyTrainArgumentParser::test_validate_args_success_and_failure` | 1 |  |
| `TestPyTrainArgumentParser::test_remove_args_makes_option_unrecognized` | 1 |  |
| `TestPyTrainArgumentParser::test_is_exit_on_error_inherits_from_parent` | 1 |  |
| `TestStripPrefixesHelpFormatter::test_usage_strips_hyphens_from_options` | 1 |  |
| `TestIntRange::test_no_bounds_accepts_ints_and_rejects_non_int` | 1 |  |
| `TestIntRange::test_min_and_max_bounds` | 1 |  |
| `TestIntRange::test_min_only` | 1 |  |
| `TestIntRange::test_max_only` | 1 |  |

## tests/utils/test_cache_directory.py

3 cases; 3 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_legacy_relative_cache_directory` | 1 | monkeypatch |
| `test_unified_cache_root` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_component_override_preserved` | 1 | monkeypatch, tmp_path, tmp_path_factory |

## tests/utils/test_dual_logging.py

10 cases; 10 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_set_up_logging_stdout_and_file_levels_and_color` | 1 | capsys, clean_logging, tmp_path, tmp_path_factory |
| `test_root_level_is_the_minimum_of_the_handler_levels` | 1 | clean_logging, tmp_path, tmp_path_factory |
| `test_root_level_follows_the_more_permissive_handler` | 1 | clean_logging, tmp_path, tmp_path_factory |
| `test_root_level_left_sane_when_file_handler_setup_fails` | 1 | clean_logging, tmp_path, tmp_path_factory |
| `test_set_log_level_moves_root_and_handlers_together` | 1 | clean_logging, tmp_path, tmp_path_factory |
| `test_set_up_logging_stderr_and_invalid_console_level` | 1 | clean_logging, tmp_path, tmp_path_factory |
| `test_set_up_logging_invalid_console_output` | 1 | clean_logging, tmp_path, tmp_path_factory |
| `test_set_up_logging_invalid_file_level` | 1 | clean_logging, tmp_path, tmp_path_factory |
| `test_console_formatter_includes_exception_trace` | 1 | clean_logging, tmp_path, tmp_path_factory |
| `test_rotating_file_handler_rollover_when_file_exists` | 1 | clean_logging, tmp_path, tmp_path_factory |

## tests/utils/test_expiring_set.py

7 cases; 7 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_add_and_contains_with_expiry` | 1 | fake_time, monkeypatch |
| `test_len_after_expiry_timestamp` | 1 | fake_time, monkeypatch |
| `test_readd_after_expiry_updates_timestamp` | 1 | fake_time, monkeypatch |
| `test_discard_and_remove` | 1 | fake_time, monkeypatch |
| `test_clear` | 1 | fake_time, monkeypatch |
| `test_dunder_contains_delegates` | 1 | fake_time, monkeypatch |
| `test_repr_is_string_and_does_not_error` | 1 | fake_time, monkeypatch |

## tests/utils/test_flatpak_updates.py

9 cases; 5 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_version_key_includes_packaging_revision` | 1 |  |
| `test_rejects_invalid_tags` | 5 | tag |
| `test_release_check_requires_complete_assets` | 1 | monkeypatch |
| `test_release_check_does_not_mutate_other_update_paths` | 1 | monkeypatch |
| `test_development_tag_ordering` | 1 |  |

## tests/utils/test_host_info.py

12 cases; 7 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_platform_is_empty_when_the_launcher_set_nothing` | 1 | monkeypatch |
| `test_platform_reports_the_steam_deck` | 1 | monkeypatch |
| `test_platform_is_normalized` | 3 | monkeypatch, value |
| `test_platform_is_read_live_rather_than_cached` | 1 | monkeypatch |
| `test_an_unrelated_platform_is_not_the_steam_deck` | 1 | monkeypatch |
| `test_is_linux_reports_the_running_system` | 4 | expected, monkeypatch, system |
| `test_is_linux_does_not_probe_the_hardware` | 1 | monkeypatch |

## tests/utils/test_image_utils.py

7 cases; 2 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_load_font_prefers_dejavu` | 3 | size |
| `test_center_text_on_image_falls_back_when_dejavu_is_missing` | 4 | font_size, styled |

## tests/utils/test_ip_tools.py

22 cases; 13 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_find_hostname_script_prefers_path` | 1 | mock_network_wait, monkeypatch, tmp_path, tmp_path_factory |
| `test_find_hostname_script_uses_python_scripts_directory` | 1 | mock_network_wait, monkeypatch, tmp_path, tmp_path_factory |
| `test_find_hostname_script_uses_source_tree_path` | 1 | mock_network_wait, monkeypatch, tmp_path, tmp_path_factory |
| `test_find_hostname_script_returns_none_when_missing` | 1 | mock_network_wait, monkeypatch, tmp_path, tmp_path_factory |
| `test_get_ip_address_linux_hostname_success` | 1 | mock_network_wait, monkeypatch |
| `test_get_ip_address_missing_hostname_uses_script` | 3 | location, mock_network_wait, monkeypatch, tmp_path, tmp_path_factory |
| `test_get_ip_address_script_failure_uses_socket` | 4 | failure, mock_network_wait, monkeypatch, tmp_path, tmp_path_factory |
| `test_get_ip_address_native_failure_does_not_use_script` | 2 | mock_network_wait, monkeypatch, returncode, stdout |
| `test_get_ip_address_command_cancellation_propagates` | 4 | exception, missing_native, mock_network_wait, monkeypatch, tmp_path, tmp_path_factory |
| `test_get_ip_address_non_linux_socket_success_filters_localhost` | 1 | mock_network_wait, monkeypatch |
| `test_get_ip_address_non_linux_retries_until_success` | 1 | mock_network_wait, monkeypatch |
| `test_is_base_address_success_and_failure` | 1 | mock_network_wait, monkeypatch |
| `test_find_base_address_returns_first_found` | 1 | mock_network_wait, monkeypatch |

## tests/utils/test_logging_manager.py

2 cases; 2 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_explicit_initialization_is_idempotent` | 1 | tmp_path, tmp_path_factory |
| `test_inherited_pid_is_not_treated_as_initialized` | 1 | tmp_path, tmp_path_factory |

## tests/utils/test_logging_multiprocessing.py

3 cases; 1 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_worker_import_does_not_rotate_main_log` | 3 | method, tmp_path, tmp_path_factory |

## tests/utils/test_path_util.py

9 cases; 9 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_find_installation_dir` | 1 |  |
| `test_find_installation_files` | 1 |  |
| `test_find_dir_simple` | 1 | tmp_path, tmp_path_factory |
| `test_find_dir_skips_hidden_and_excluded_dirs` | 1 | tmp_path, tmp_path_factory |
| `test_find_file_simple` | 1 | tmp_path, tmp_path_factory |
| `test_find_file_skips_hidden_files` | 1 | tmp_path, tmp_path_factory |
| `test_find_file_skips_excluded_dirs` | 1 | tmp_path, tmp_path_factory |
| `test_find_dir_not_found` | 1 | tmp_path, tmp_path_factory |
| `test_find_file_not_found` | 1 | tmp_path, tmp_path_factory |

## tests/utils/test_path_utils.py

9 cases; 9 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_resolution_parity_against_reference` | 1 | tmp_path, tmp_path_factory |
| `test_first_match_ordering_across_places` | 1 | tmp_path, tmp_path_factory |
| `test_single_walk_for_default_places` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_miss_is_cached_and_reset_hook` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_non_default_places_are_fresh` | 1 | tmp_path, tmp_path_factory |
| `test_concrete_path_short_circuit` | 1 | tmp_path, tmp_path_factory |
| `test_venv_style_dirs_are_pruned` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_find_packaged_asset_outside_working_directory` | 1 | monkeypatch, tmp_path, tmp_path_factory |
| `test_explicit_cache_root_under_hidden_parent` | 1 | tmp_path, tmp_path_factory |

## tests/utils/test_pollable_queue.py

5 cases; 5 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_fileno_is_valid` | 1 |  |
| `test_select_ready_on_put_and_clears_on_get` | 1 |  |
| `test_multiple_puts_and_gets_signal_and_drain` | 1 |  |
| `test_put_when_full_does_not_signal_extra_bytes` | 1 |  |
| `test_non_posix_fallback_socket_pair` | 1 | monkeypatch |

## tests/utils/test_singleton.py

5 cases; 5 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_returns_same_instance_and_init_called_once` | 1 |  |
| `test_thread_safety_singleton_single_instance` | 1 |  |
| `test_different_singleton_classes_are_independent` | 1 |  |
| `test_repeated_calls_do_not_change_state` | 1 |  |
| `test_initialized_flag_present_and_true_on_bar` | 1 |  |

## tests/utils/test_text_utils.py

6 cases; 6 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_none_and_empty` | 1 |  |
| `test_sd70ace_variants_compact_and_split` | 1 |  |
| `test_sd80mac_variants_compact_and_split` | 1 |  |
| `test_preserve_series_codes_and_patterns` | 1 |  |
| `test_general_capitalization_and_short_words` | 1 |  |
| `test_multi_word_mixed_cases` | 1 |  |

## tests/utils/test_unique_deque.py

20 cases; 20 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestUniqueDequeue::test_create_no_args` | 1 |  |
| `TestUniqueDequeue::test_getters_fail_on_zero_len_unique_deque` | 1 |  |
| `TestUniqueDequeue::test_clear` | 1 |  |
| `TestUniqueDequeue::test_insert_basic` | 1 |  |
| `TestUniqueDequeue::test_insert_existing_moves_item` | 1 |  |
| `TestUniqueDequeue::test_insert_boundaries` | 1 |  |
| `TestUniqueDequeue::test_remove` | 1 |  |
| `TestUniqueDequeue::test_popleft` | 1 |  |
| `TestUniqueDequeue::test_pop` | 1 |  |
| `TestUniqueDequeue::test_extendleft` | 1 |  |
| `TestUniqueDequeue::test_extend` | 1 |  |
| `TestUniqueDequeue::test_copy` | 1 |  |
| `TestUniqueDequeue::test_appendleft` | 1 |  |
| `TestUniqueDequeue::test_append` | 1 |  |
| `TestUniqueDequeue::test_maxlen_eviction_append_and_appendleft` | 1 |  |
| `TestUniqueDequeue::test_uniqueness_moves_existing_to_ends` | 1 |  |
| `TestUniqueDequeue::test_add_returns_new_and_iadd_mutates` | 1 |  |
| `TestUniqueDequeue::test_setitem_behavior_for_existing_and_new_values` | 1 |  |
| `TestUniqueDequeue::test_push_alias_for_appendleft` | 1 |  |
| `TestUniqueDequeue::test_not_implemented_ops` | 1 |  |

## tests/utils/test_validations.py

24 cases; 24 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `TestValidateInt::test_returns_int_when_already_int` | 1 |  |
| `TestValidateInt::test_converts_string_digits_to_int` | 1 |  |
| `TestValidateInt::test_allows_none_when_flag_true` | 1 |  |
| `TestValidateInt::test_raises_type_error_for_non_castable_type` | 1 |  |
| `TestValidateInt::test_raises_value_error_for_non_numeric_string_default_label` | 1 |  |
| `TestValidateInt::test_raises_value_error_for_non_numeric_string_custom_label` | 1 |  |
| `TestValidateInt::test_min_value_enforced_no_label` | 1 |  |
| `TestValidateInt::test_min_value_enforced_with_label_and_suffix` | 1 |  |
| `TestValidateInt::test_max_value_enforced_no_label` | 1 |  |
| `TestValidateInt::test_max_value_enforced_with_label_and_suffix` | 1 |  |
| `TestValidateInt::test_boundary_values_ok` | 1 |  |
| `TestValidateInt::test_value_inside_bounds_ok` | 1 |  |
| `TestValidateFloat::test_returns_float_when_already_float` | 1 |  |
| `TestValidateFloat::test_converts_int_to_float` | 1 |  |
| `TestValidateFloat::test_converts_string_number_to_float` | 1 |  |
| `TestValidateFloat::test_allows_none_when_flag_true` | 1 |  |
| `TestValidateFloat::test_raises_value_error_for_non_numeric_string_default_label` | 1 |  |
| `TestValidateFloat::test_raises_value_error_for_non_numeric_string_custom_label` | 1 |  |
| `TestValidateFloat::test_min_value_enforced_no_label` | 1 |  |
| `TestValidateFloat::test_min_value_enforced_with_label_and_suffix` | 1 |  |
| `TestValidateFloat::test_max_value_enforced_no_label` | 1 |  |
| `TestValidateFloat::test_max_value_enforced_with_label_and_suffix` | 1 |  |
| `TestValidateFloat::test_boundary_values_ok` | 1 |  |
| `TestValidateFloat::test_value_inside_bounds_ok` | 1 |  |

## tests/utils/test_wifi_info.py

5 cases; 5 families. Retain unless mapped to a survivor in the main report.

| Family | Cases | Fixture closure |
|---|---:|---|
| `test_dbm_to_quality_clamps_to_zero_and_one_hundred` | 1 |  |
| `test_linux_iw_uses_discovered_interface_not_wlan0` | 1 | monkeypatch |
| `test_linux_iw_reuses_cached_interface_on_later_queries` | 1 | monkeypatch |
| `test_linux_procfs_fallback_reads_signal_from_proc_net_wireless` | 1 | monkeypatch |
| `test_macos_airport_output_is_parsed` | 1 | monkeypatch |
