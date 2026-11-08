# Measured rankings

Final Step 4 profile, October 21, 2026: `step4-profile-1`, `-2`, and `-3`.
See [the audit](../test-suite-audit.md#step-4-smoke-selection-and-final-verification)
for commands, environment, ordinary timings, and comparison limitations.

Seconds; median across three runs. Module/family totals include setup, call, and teardown.

## Individual phases

| Item | Median | Min | Max |
|---|---:|---:|---:|
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[spawn] (call)` | 0.609852 | 0.596662 | 0.611247 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[forkserver] (call)` | 0.584909 | 0.577932 | 0.596593 |
| `tests/db/test_cache_sync.py::test_stop_without_listener_terminates_real_worker (call)` | 0.502355 | 0.500967 | 0.502777 |
| `tests/gui/controller/test_controls_panel.py::test_a_measured_ruler_reports_the_font_tk_will_draw_in (call)` | 0.357825 | 0.347366 | 0.382096 |
| `tests/gui/test_route_builder_panel.py::test_successful_clear_hides_panel_through_popup_manager (call)` | 0.320642 | 0.303404 | 0.320738 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[fork] (call)` | 0.316020 | 0.315622 | 0.321441 |
| `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath[True] (call)` | 0.298566 | 0.296242 | 0.300247 |
| `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath[False] (call)` | 0.295628 | 0.292751 | 0.300179 |
| `tests/gui/controller/test_engine_gui_compatibility.py::test_default_constructor_preserves_standalone_portrait_options (call)` | 0.217316 | 0.215391 | 0.217962 |
| `tests/gui/test_image_presenter.py::test_update_ignores_stale_engine_callback_for_other_scope (call)` | 0.214397 | 0.206656 | 0.215442 |
| `tests/cli/test_lcs.py::test_host_defaults_to_the_portrait_overlay_geometry (call)` | 0.213458 | 0.213155 | 0.213813 |
| `tests/protocol/sequence/test_speed_ramp.py::TestSpeedRamp::test_an_abort_waits_for_a_step_already_on_the_wire (call)` | 0.201338 | 0.201311 | 0.201374 |
| `tests/utils/test_path_util.py::test_find_installation_dir (call)` | 0.174976 | 0.172528 | 0.175156 |
| `tests/test_pytest.py::TestPyTrain::test_get_version (call)` | 0.119895 | 0.119279 | 0.126643 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[False-0-40-False-darwin] (setup)` | 0.101029 | 0.100178 | 0.104861 |
| `tests/gui/test_component_state_gui.py::test_cycle_gui_ignores_unknown_key (call)` | 0.100310 | 0.100251 | 0.100797 |
| `tests/protocol/sequence/test_ramp_peer.py::test_timestamp_race_converges_without_startup_echo[False-False-3180-CommandScope.ENGINE] (call)` | 0.097034 | 0.000887 | 0.106638 |
| `tests/gui/test_route_builder_panel.py::test_picker_size_and_page_navigation_follow_available_layout[480-800-True-linux-330-38] (call)` | 0.083283 | 0.081364 | 0.083361 |
| `tests/gui/test_checkbox_group.py::test_the_cursor_tints_the_row_it_is_moved_to (call)` | 0.071660 | 0.065683 | 0.073078 |
| `tests/cli/test_make_gui.py::test_make_gui_parser_accepts_no_cache_sync (call)` | 0.070352 | 0.070212 | 0.070566 |
| `tests/cli/test_make_service.py::TestMakeService::test_parser (call)` | 0.053672 | 0.053067 | 0.054216 |
| `tests/cli/test_cache_sync_service.py::test_shutdown_cache_retains_manager_on_failure_then_retries[2-KeyboardInterrupt] (call)` | 0.053263 | 0.049828 | 0.054332 |
| `tests/cli/test_make_gui.py::test_other_guis_still_autostart_unconditionally (call)` | 0.051559 | 0.051225 | 0.054969 |
| `tests/protocol/sequence/test_speed_ramp.py::TestSpeedRamp::test_an_abort_stalled_on_the_wire_still_completes (call)` | 0.051432 | 0.050482 | 0.051434 |
| `tests/cli/test_make_gui.py::test_desktop_autostart_abbreviates (call)` | 0.051314 | 0.050541 | 0.051443 |

## Individual cases

| Item | Median | Min | Max |
|---|---:|---:|---:|
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[spawn]` | 0.611309 | 0.598020 | 0.612633 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[forkserver]` | 0.586242 | 0.579205 | 0.598172 |
| `tests/db/test_cache_sync.py::test_stop_without_listener_terminates_real_worker` | 0.502661 | 0.501288 | 0.503046 |
| `tests/gui/controller/test_controls_panel.py::test_a_measured_ruler_reports_the_font_tk_will_draw_in` | 0.357993 | 0.347525 | 0.382304 |
| `tests/gui/test_route_builder_panel.py::test_successful_clear_hides_panel_through_popup_manager` | 0.323731 | 0.306460 | 0.324164 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[fork]` | 0.316917 | 0.316663 | 0.322401 |
| `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath[True]` | 0.299837 | 0.297415 | 0.301522 |
| `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath[False]` | 0.296479 | 0.293614 | 0.301042 |
| `tests/gui/controller/test_engine_gui_compatibility.py::test_default_constructor_preserves_standalone_portrait_options` | 0.217517 | 0.215586 | 0.218187 |
| `tests/gui/test_image_presenter.py::test_update_ignores_stale_engine_callback_for_other_scope` | 0.214594 | 0.206852 | 0.215655 |
| `tests/cli/test_lcs.py::test_host_defaults_to_the_portrait_overlay_geometry` | 0.213967 | 0.213677 | 0.214043 |
| `tests/protocol/sequence/test_speed_ramp.py::TestSpeedRamp::test_an_abort_waits_for_a_step_already_on_the_wire` | 0.202486 | 0.202415 | 0.202609 |
| `tests/utils/test_path_util.py::test_find_installation_dir` | 0.175173 | 0.172736 | 0.175423 |
| `tests/test_pytest.py::TestPyTrain::test_get_version` | 0.120280 | 0.119689 | 0.127107 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[False-0-40-False-darwin]` | 0.101911 | 0.100886 | 0.105587 |
| `tests/gui/test_component_state_gui.py::test_cycle_gui_ignores_unknown_key` | 0.100567 | 0.100475 | 0.101043 |
| `tests/protocol/sequence/test_ramp_peer.py::test_timestamp_race_converges_without_startup_echo[False-False-3180-CommandScope.ENGINE]` | 0.098073 | 0.001883 | 0.107757 |
| `tests/gui/test_route_builder_panel.py::test_picker_size_and_page_navigation_follow_available_layout[480-800-True-linux-330-38]` | 0.086531 | 0.084451 | 0.086663 |
| `tests/gui/test_checkbox_group.py::test_the_cursor_tints_the_row_it_is_moved_to` | 0.071912 | 0.065889 | 0.073281 |
| `tests/cli/test_make_gui.py::test_make_gui_parser_accepts_no_cache_sync` | 0.070683 | 0.070509 | 0.070873 |
| `tests/cli/test_cache_sync_service.py::test_shutdown_cache_retains_manager_on_failure_then_retries[2-KeyboardInterrupt]` | 0.054319 | 0.050908 | 0.055316 |
| `tests/cli/test_make_service.py::TestMakeService::test_parser` | 0.054058 | 0.053507 | 0.054638 |
| `tests/protocol/sequence/test_speed_ramp.py::TestSpeedRamp::test_an_abort_stalled_on_the_wire_still_completes` | 0.052538 | 0.051416 | 0.052563 |
| `tests/cli/test_make_gui.py::test_other_guis_still_autostart_unconditionally` | 0.051861 | 0.051572 | 0.055362 |
| `tests/cli/test_make_gui.py::test_desktop_autostart_abbreviates` | 0.051690 | 0.050883 | 0.051768 |

## Modules

| Item | Median | Min | Max |
|---|---:|---:|---:|
| `tests/utils/test_logging_multiprocessing.py` | 1.514214 | 1.494142 | 1.533206 |
| `tests/gui/test_route_builder_panel.py` | 1.409666 | 1.380297 | 1.428475 |
| `tests/cli/test_routes.py` | 0.623511 | 0.623056 | 0.632078 |
| `tests/db/test_cache_sync.py` | 0.544698 | 0.541371 | 0.545439 |
| `tests/cli/test_pytrain.py` | 0.448232 | 0.445198 | 0.451707 |
| `tests/gui/controller/test_controls_panel.py` | 0.433995 | 0.428871 | 0.460718 |
| `tests/protocol/sequence/test_speed_ramp_geometry.py` | 0.404440 | 0.387845 | 0.410958 |
| `tests/protocol/sequence/test_speed_ramp.py` | 0.359599 | 0.352716 | 0.361234 |
| `tests/cli/test_make_gui.py` | 0.340420 | 0.338608 | 0.346140 |
| `tests/gui/test_lcs_config_panel.py` | 0.306866 | 0.297908 | 0.307569 |
| `tests/protocol/multibyte/test_ramp_command_req.py` | 0.272625 | 0.271505 | 0.279232 |
| `tests/cli/test_pytrain_runtime.py` | 0.238504 | 0.237259 | 0.239234 |
| `tests/gui/controller/test_engine_gui_compatibility.py` | 0.235156 | 0.232755 | 0.236246 |
| `tests/cli/test_lcs.py` | 0.224942 | 0.224645 | 0.224991 |
| `tests/gui/test_image_presenter.py` | 0.216459 | 0.208680 | 0.217563 |
| `tests/db/test_comp_data.py` | 0.185818 | 0.181706 | 0.190667 |
| `tests/utils/test_path_util.py` | 0.183317 | 0.180324 | 0.183541 |
| `tests/protocol/sequence/test_ramp_peer.py` | 0.175379 | 0.169182 | 0.178196 |
| `tests/protocol/test_command_req.py` | 0.169379 | 0.167094 | 0.171284 |
| `tests/pdi/test_base_req.py` | 0.164075 | 0.160252 | 0.166385 |
| `tests/gui/controller/test_steam_deck_input.py` | 0.148010 | 0.147252 | 0.149476 |
| `tests/cli/test_pytrain_commands.py` | 0.145254 | 0.145185 | 0.145761 |
| `tests/cli/test_pytrain_pdi.py` | 0.140889 | 0.140068 | 0.141027 |
| `tests/gui/test_component_state_gui.py` | 0.134595 | 0.133822 | 0.135090 |
| `tests/protocol/test_speed_to_rpm.py` | 0.126524 | 0.123410 | 0.126588 |
| `tests/cli/test_pytrain_admin.py` | 0.122739 | 0.120808 | 0.123184 |
| `tests/test_pytest.py` | 0.120953 | 0.120389 | 0.127786 |
| `tests/gui/test_checkbox_group.py` | 0.106623 | 0.100876 | 0.108864 |
| `tests/gui/test_routes_gui.py` | 0.101335 | 0.096040 | 0.101868 |
| `tests/db/test_engine_state_core.py` | 0.084890 | 0.082802 | 0.085295 |
| `tests/cli/test_cache_sync_service.py` | 0.083177 | 0.080939 | 0.085743 |
| `tests/cli/test_pytrain_service_discovery.py` | 0.066155 | 0.062983 | 0.066459 |
| `tests/cli/test_pytrain_state.py` | 0.064311 | 0.063782 | 0.066434 |
| `tests/protocol/sequence/test_ramp_speed_req.py` | 0.061786 | 0.060120 | 0.062736 |
| `tests/cli/test_pytrain_update.py` | 0.058019 | 0.057517 | 0.059813 |
| `tests/protocol/sequence/test_two_controller_ramp.py` | 0.057772 | 0.054985 | 0.061653 |
| `tests/comm/test_command_listener_ai.py` | 0.057409 | 0.053775 | 0.058344 |
| `tests/cli/test_make_service.py` | 0.056902 | 0.056431 | 0.057891 |
| `tests/protocol/sequence/test_speed_ramp_echoes.py` | 0.056189 | 0.054977 | 0.058480 |
| `tests/gui/test_keypad_view.py` | 0.055148 | 0.053652 | 0.058845 |
| `tests/gui/test_controller_view.py` | 0.053505 | 0.053262 | 0.054218 |
| `tests/gui/test_editable_text.py` | 0.052099 | 0.052065 | 0.056087 |
| `tests/utils/test_path_utils.py` | 0.048965 | 0.047331 | 0.049412 |
| `tests/db/test_engine_state.py` | 0.045213 | 0.044578 | 0.046351 |
| `tests/db/test_prod_info.py` | 0.042668 | 0.042647 | 0.042823 |
| `tests/comm/test_dispatch_listener.py` | 0.042359 | 0.042355 | 0.044349 |
| `tests/pdi/test_irda_req.py` | 0.041596 | 0.040458 | 0.042757 |
| `tests/db/test_ramp_claim_state.py` | 0.040811 | 0.040261 | 0.043251 |
| `tests/db/test_irda_state.py` | 0.037093 | 0.036135 | 0.037193 |
| `tests/gui/controller/test_accessory_bindings.py` | 0.034548 | 0.033999 | 0.035192 |
| `tests/gui/test_guizero_base.py` | 0.031459 | 0.030697 | 0.031776 |
| `tests/utils/test_ip_tools.py` | 0.028882 | 0.028200 | 0.029186 |
| `tests/gui/test_gui_checkpoint.py` | 0.027949 | 0.027258 | 0.028949 |
| `tests/gui/test_gui_deck_parity.py` | 0.026068 | 0.024388 | 0.026468 |
| `tests/protocol/sequence/test_ramp_residuals.py` | 0.025999 | 0.025066 | 0.027510 |
| `tests/protocol/multibyte/test_ramp_listener.py` | 0.025459 | 0.024623 | 0.025742 |
| `tests/db/test_component_state.py` | 0.025065 | 0.025021 | 0.025142 |
| `tests/gui/test_route_draft.py` | 0.023034 | 0.022532 | 0.023887 |
| `tests/gui/controller/test_controller_view_throttle.py` | 0.022402 | 0.022278 | 0.022687 |
| `tests/db/test_component_state_store_ai.py` | 0.022238 | 0.021529 | 0.022485 |
| `tests/cli/test_pycab.py` | 0.021281 | 0.021087 | 0.021601 |
| `tests/test_deck_packaging.py` | 0.019224 | 0.018485 | 0.019352 |
| `tests/gui/test_steam_deck_gui.py` | 0.018794 | 0.018740 | 0.018891 |
| `tests/cli/test_configure.py` | 0.018387 | 0.017234 | 0.019694 |
| `tests/gui/controller/test_control_labels.py` | 0.018259 | 0.017240 | 0.018337 |
| `tests/gui/test_lcs_device_registry.py` | 0.017404 | 0.016723 | 0.017486 |
| `tests/gui/test_scroll_box.py` | 0.017202 | 0.016940 | 0.018314 |
| `tests/cli/test_pytrain_debug_toggle.py` | 0.016604 | 0.016426 | 0.016652 |
| `tests/gui/test_engine_gui_create.py` | 0.015873 | 0.015301 | 0.015926 |
| `tests/protocol/sequence/test_ramp_registry.py` | 0.015797 | 0.015314 | 0.015907 |
| `tests/gui/test_engine_gui_accessories.py` | 0.014911 | 0.014900 | 0.015162 |
| `tests/gui/controller/test_popup_manager_compatibility.py` | 0.014593 | 0.014524 | 0.015473 |
| `tests/gui/test_hold_button.py` | 0.013131 | 0.012816 | 0.013214 |
| `tests/gui/controller/test_admin_panel_layout.py` | 0.012069 | 0.011991 | 0.012403 |
| `tests/gui/test_bundled_fonts.py` | 0.011940 | 0.011742 | 0.012400 |
| `tests/comm/test_comm_buffer_proxy_disconnect.py` | 0.011821 | 0.011290 | 0.011895 |
| `tests/gui/test_lcs_sequence_builder.py` | 0.011435 | 0.011201 | 0.011717 |
| `tests/gui/test_lcs_imports.py` | 0.011423 | 0.011292 | 0.011505 |
| `tests/gui/test_lcs_id_map.py` | 0.011381 | 0.011131 | 0.011704 |
| `tests/gui/accessory/test_accessory_gui.py` | 0.008935 | 0.008501 | 0.009474 |
| `tests/utils/test_dual_logging.py` | 0.008470 | 0.008371 | 0.009494 |
| `tests/gui/test_touch_list_box.py` | 0.007971 | 0.007883 | 0.007998 |
| `tests/gui/test_swipe_detector.py` | 0.007719 | 0.007271 | 0.007958 |
| `tests/db/test_components.py` | 0.007697 | 0.007413 | 0.007711 |
| `tests/db/test_lcs_state_serialization.py` | 0.007564 | 0.007242 | 0.007573 |
| `tests/utils/test_image_utils.py` | 0.007329 | 0.007126 | 0.007448 |
| `tests/gui/test_scroll_input.py` | 0.006872 | 0.006680 | 0.006957 |
| `tests/utils/test_validations.py` | 0.006442 | 0.006304 | 0.007110 |
| `tests/gui/test_engine_gui_transitions.py` | 0.006395 | 0.006151 | 0.006746 |
| `tests/gui/test_pycab_app.py` | 0.006087 | 0.006071 | 0.006176 |
| `tests/gui/test_motors_gui.py` | 0.005532 | 0.005345 | 0.005699 |
| `tests/db/test_accessory_state.py` | 0.005243 | 0.005133 | 0.005614 |
| `tests/db/test_component_state_store.py` | 0.004811 | 0.004596 | 0.005623 |
| `tests/db/test_startup_state.py` | 0.004754 | 0.004223 | 0.005373 |
| `tests/protocol/test_tmcc1_acc_aux_numbers.py` | 0.004647 | 0.004513 | 0.004862 |
| `tests/gui/test_amc2_ops_panel.py` | 0.004555 | 0.004483 | 0.004605 |
| `tests/comm/test_enqueue_proxy_requests.py` | 0.004228 | 0.004094 | 0.004452 |
| `tests/comm/test_command_listener.py` | 0.003919 | 0.003639 | 0.003950 |
| `tests/integration/test_pytrain_api_exit.py` | 0.003752 | 0.003712 | 0.003807 |
| `tests/gui/controller/test_flatpak_admin_actions.py` | 0.003540 | 0.003477 | 0.003925 |
| `tests/gpio/utils/test_text_buffer.py` | 0.003387 | 0.003309 | 0.003569 |
| `tests/utils/test_unique_deque.py` | 0.003376 | 0.003096 | 0.003510 |
| `tests/pdi/test_constants.py` | 0.003346 | 0.003342 | 0.005370 |
| `tests/pdi/test_base3_buffer.py` | 0.003343 | 0.003204 | 0.003511 |
| `tests/protocol/test_constants.py` | 0.003279 | 0.003124 | 0.003816 |
| `tests/gui/test_catalog_panel.py` | 0.003166 | 0.003023 | 0.003189 |
| `tests/gui/test_dummy_gui_components.py` | 0.003155 | 0.003017 | 0.003160 |
| `tests/pdi/test_pdi_listener.py` | 0.003128 | 0.003047 | 0.003726 |
| `tests/gui/test_lcs_icons.py` | 0.003035 | 0.002916 | 0.003254 |
| `tests/cli/test_ancillary_logging.py` | 0.002943 | 0.002669 | 0.003024 |
| `tests/gui/test_accessory_cache_root.py` | 0.002938 | 0.002897 | 0.003080 |
| `tests/pdi/test_pdi_req.py` | 0.002905 | 0.002720 | 0.003023 |
| `tests/utils/test_singleton.py` | 0.002713 | 0.002641 | 0.002868 |
| `tests/gui/test_touch_list.py` | 0.002671 | 0.002666 | 0.002714 |
| `tests/utils/test_host_info.py` | 0.002602 | 0.002528 | 0.002737 |
| `tests/utils/test_argument_parser.py` | 0.002533 | 0.002491 | 0.002630 |
| `tests/db/test_client_state_listener.py` | 0.002464 | 0.002305 | 0.002622 |
| `tests/pdi/test_lcs_req.py` | 0.002417 | 0.002347 | 0.002549 |
| `tests/gpio/i2c/test_mcp23017.py` | 0.002289 | 0.002149 | 0.002297 |
| `tests/gui/test_wide_component_state_gui.py` | 0.002269 | 0.002200 | 0.002735 |
| `tests/utils/test_logging_manager.py` | 0.002246 | 0.002138 | 0.002303 |
| `tests/gui/test_state_info_overlay.py` | 0.002222 | 0.002215 | 0.002276 |
| `tests/utils/test_flatpak_updates.py` | 0.002063 | 0.002024 | 0.002656 |
| `tests/pdi/test_asc2_req.py` | 0.001871 | 0.001780 | 0.001985 |
| `tests/utils/test_wifi_info.py` | 0.001843 | 0.001688 | 0.001847 |
| `tests/pdi/test_amc2_req.py` | 0.001774 | 0.001763 | 0.001929 |
| `tests/gui/controller/test_flatpak_update_indicator.py` | 0.001751 | 0.001748 | 0.002176 |
| `tests/gui/accessory/test_accessory_registry.py` | 0.001711 | 0.001554 | 0.001933 |
| `tests/gui/controller/test_engine_gui_conf_import.py` | 0.001675 | 0.001666 | 0.001703 |
| `tests/atc/test_block.py` | 0.001675 | 0.001494 | 0.001799 |
| `tests/utils/test_cache_directory.py` | 0.001643 | 0.001568 | 0.001699 |
| `tests/db/test_state_watcher.py` | 0.001571 | 0.001554 | 0.001608 |
| `tests/pdi/test_d4_req.py` | 0.001556 | 0.001421 | 0.001630 |
| `tests/gui/controller/test_rr_speed_panel.py` | 0.001525 | 0.001466 | 0.001776 |
| `tests/utils/test_expiring_set.py` | 0.001497 | 0.001437 | 0.001628 |
| `tests/gui/controller/test_bell_horn_panel.py` | 0.001472 | 0.001429 | 0.001487 |
| `tests/pdi/test_bpc2_req.py` | 0.001355 | 0.001315 | 0.001376 |
| `tests/gui/test_touch_scrollbar.py` | 0.001330 | 0.001297 | 0.001367 |
| `tests/test_version_tuple.py` | 0.001309 | 0.001301 | 0.001434 |
| `tests/pdi/test_pdi_state_store.py` | 0.001309 | 0.001284 | 0.001698 |
| `tests/gui/controller/test_steam_deck_packaging.py` | 0.001297 | 0.001278 | 0.001414 |
| `tests/pdi/test_stm2_req.py` | 0.001252 | 0.001204 | 0.001308 |
| `tests/utils/test_pollable_queue.py` | 0.001211 | 0.001140 | 0.001245 |
| `tests/gui/test_scrolling_text.py` | 0.001185 | 0.001154 | 0.001304 |
| `tests/utils/test_text_utils.py` | 0.001170 | 0.001008 | 0.001249 |
| `tests/gpio/i2c/test_i2c.py` | 0.001157 | 0.001120 | 0.001299 |
| `tests/cli/test_cache.py` | 0.001119 | 0.001079 | 0.001179 |
| `tests/gui/accessory/test_accessories_gui_catalog.py` | 0.001117 | 0.001099 | 0.001215 |
| `tests/gpio/test_engine_status.py` | 0.001041 | 0.001037 | 0.001174 |
| `tests/gui/test_lcs_panel_wiring.py` | 0.000872 | 0.000855 | 0.000953 |
| `tests/gpio/test_gpio_device.py` | 0.000270 | 0.000266 | 0.000285 |
| `tests/test_update_policy.py` | 0.000230 | 0.000225 | 0.000406 |
| `tests/protocol/test_command_base.py` | 0.000202 | 0.000191 | 0.000279 |
| `tests/gui/accessory/test_station_gui.py` | 0.000183 | 0.000180 | 0.000190 |

## Parameter families

| Item | Median | Min | Max |
|---|---:|---:|---:|
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log` | 1.514214 | 1.494142 | 1.533206 |
| `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath` | 0.593894 | 0.593451 | 0.602564 |
| `tests/db/test_cache_sync.py::test_stop_without_listener_terminates_real_worker` | 0.502661 | 0.501288 | 0.503046 |
| `tests/gui/controller/test_controls_panel.py::test_a_measured_ruler_reports_the_font_tk_will_draw_in` | 0.357993 | 0.347525 | 0.382304 |
| `tests/cli/test_pytrain.py::test_parser_rejects_invalid_options` | 0.342637 | 0.339551 | 0.346564 |
| `tests/gui/test_route_builder_panel.py::test_successful_clear_hides_panel_through_popup_manager` | 0.323731 | 0.306460 | 0.324164 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing` | 0.245181 | 0.237282 | 0.253475 |
| `tests/gui/controller/test_engine_gui_compatibility.py::test_default_constructor_preserves_standalone_portrait_options` | 0.217517 | 0.215586 | 0.218187 |
| `tests/gui/test_image_presenter.py::test_update_ignores_stale_engine_callback_for_other_scope` | 0.214594 | 0.206852 | 0.215655 |
| `tests/cli/test_lcs.py::test_host_defaults_to_the_portrait_overlay_geometry` | 0.213967 | 0.213677 | 0.214043 |
| `tests/protocol/sequence/test_speed_ramp.py::TestSpeedRamp::test_an_abort_waits_for_a_step_already_on_the_wire` | 0.202486 | 0.202415 | 0.202609 |
| `tests/utils/test_path_util.py::test_find_installation_dir` | 0.175173 | 0.172736 | 0.175423 |
| `tests/protocol/sequence/test_ramp_peer.py::test_timestamp_race_converges_without_startup_echo` | 0.133930 | 0.129435 | 0.138819 |
| `tests/protocol/multibyte/test_ramp_command_req.py::test_variable_target_speed_roundtrip` | 0.133235 | 0.132070 | 0.140327 |
| `tests/test_pytest.py::TestPyTrain::test_get_version` | 0.120280 | 0.119689 | 0.127107 |
| `tests/cli/test_pytrain_pdi.py::test_pdi_requests` | 0.119811 | 0.117458 | 0.120450 |
| `tests/gui/test_route_builder_panel.py::test_picker_size_and_page_navigation_follow_available_layout` | 0.110758 | 0.107428 | 0.110880 |
| `tests/gui/test_component_state_gui.py::test_cycle_gui_ignores_unknown_key` | 0.100567 | 0.100475 | 0.101043 |
| `tests/protocol/sequence/test_speed_ramp_geometry.py::TestSpeedRampGeometry::test_bias_derived_from_the_base_table_and_clamped` | 0.097403 | 0.093967 | 0.099508 |
| `tests/protocol/sequence/test_speed_ramp_geometry.py::TestSpeedRampGeometry::test_biased_rpm_on_a_scaled_map` | 0.075013 | 0.072286 | 0.077859 |
| `tests/protocol/sequence/test_speed_ramp_geometry.py::TestSpeedRampGeometry::test_biased_rpm_is_table_plus_bias_clamped` | 0.074767 | 0.071593 | 0.074910 |
| `tests/cli/test_pytrain_runtime.py::test_escaping_cleanup_error_never_dispatches_action` | 0.074368 | 0.073113 | 0.074385 |
| `tests/gui/test_checkbox_group.py::test_the_cursor_tints_the_row_it_is_moved_to` | 0.071912 | 0.065889 | 0.073281 |
| `tests/protocol/sequence/test_speed_ramp_geometry.py::TestSpeedRampGeometry::test_bias_derived_from_the_engines_own_scaled_map` | 0.071902 | 0.067043 | 0.072251 |
| `tests/cli/test_make_gui.py::test_make_gui_parser_accepts_no_cache_sync` | 0.070683 | 0.070509 | 0.070873 |

## Setup phases

| Item | Median | Min | Max |
|---|---:|---:|---:|
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[False-0-40-False-darwin]` | 0.101029 | 0.100178 | 0.104861 |
| `tests/gui/test_route_builder_panel.py::test_desktop_picker_double_click_outside_rows_does_not_add_selection[darwin-above]` | 0.005261 | 0.004923 | 0.005582 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[True-25-0-True-darwin]` | 0.005117 | 0.004093 | 0.005153 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[True-0-0-True-darwin]` | 0.004908 | 0.004884 | 0.005138 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[True--30-2-False-darwin]` | 0.004729 | 0.004332 | 0.005854 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[True--25-0-False-darwin]` | 0.004700 | 0.004339 | 0.005292 |
| `tests/gui/test_route_builder_panel.py::test_windows_retains_its_existing_scroll_bindings[win32]` | 0.004559 | 0.004420 | 0.005131 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[True-0-1-False-darwin]` | 0.004547 | 0.004353 | 0.005873 |
| `tests/gui/test_route_builder_panel.py::test_pi_button_resize_is_scheduled_once_and_retained_in_picker` | 0.004538 | 0.004398 | 0.004566 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[True-0--40-True-darwin]` | 0.004502 | 0.004296 | 0.004849 |
| `tests/gui/test_route_builder_panel.py::test_pi_buttons_resize_stably_and_shrink_when_space_is_reduced` | 0.004472 | 0.004377 | 0.004629 |
| `tests/gui/test_route_builder_panel.py::test_desktop_picker_keys_select_and_reveal_without_adding[win32]` | 0.004436 | 0.004186 | 0.004530 |
| `tests/gui/test_route_builder_panel.py::test_desktop_picker_double_click_outside_rows_does_not_add_selection[win32-above]` | 0.004427 | 0.004153 | 0.004625 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[False-0-0-True-darwin]` | 0.004421 | 0.004173 | 0.004718 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[False--30-2-False-darwin]` | 0.004415 | 0.004184 | 0.004595 |
| `tests/gui/test_route_builder_panel.py::test_desktop_wheel_browses_both_lists[darwin--1-1-False]` | 0.004351 | 0.004031 | 0.004559 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[False-25-0-True-darwin]` | 0.004329 | 0.003925 | 0.004449 |
| `tests/gui/test_route_builder_panel.py::test_pi_button_resize_ignores_unavailable_editor_geometry[hidden]` | 0.004260 | 0.004217 | 0.004387 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[False-0-1-False-darwin]` | 0.004255 | 0.004017 | 0.004340 |
| `tests/gui/test_route_builder_panel.py::test_desktop_wheel_browses_both_lists[win32--1-1-False]` | 0.004255 | 0.003798 | 0.004715 |
| `tests/gui/test_route_builder_panel.py::test_deck_picker_a_keeps_existing_component_validation[sequence_control-0-self_route]` | 0.004160 | 0.003581 | 0.004322 |
| `tests/gui/test_route_builder_panel.py::test_desktop_wheel_browses_both_lists[win32-120--1-False]` | 0.004152 | 0.004115 | 0.005142 |
| `tests/gui/test_route_builder_panel.py::test_desktop_wheel_browses_both_lists[win32--240-2-True]` | 0.004137 | 0.004001 | 0.004343 |
| `tests/gui/test_route_builder_panel.py::test_desktop_picker_double_click_adds_scrolled_component_and_returns_to_main[darwin-Routes]` | 0.004136 | 0.004115 | 0.004486 |
| `tests/gui/test_routes_gui.py::test_create_opens_draft_and_cancel_returns_to_front_without_creating_record[1]` | 0.004122 | 0.004059 | 0.004683 |

## Call phases

| Item | Median | Min | Max |
|---|---:|---:|---:|
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[spawn]` | 0.609852 | 0.596662 | 0.611247 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[forkserver]` | 0.584909 | 0.577932 | 0.596593 |
| `tests/db/test_cache_sync.py::test_stop_without_listener_terminates_real_worker` | 0.502355 | 0.500967 | 0.502777 |
| `tests/gui/controller/test_controls_panel.py::test_a_measured_ruler_reports_the_font_tk_will_draw_in` | 0.357825 | 0.347366 | 0.382096 |
| `tests/gui/test_route_builder_panel.py::test_successful_clear_hides_panel_through_popup_manager` | 0.320642 | 0.303404 | 0.320738 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[fork]` | 0.316020 | 0.315622 | 0.321441 |
| `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath[True]` | 0.298566 | 0.296242 | 0.300247 |
| `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath[False]` | 0.295628 | 0.292751 | 0.300179 |
| `tests/gui/controller/test_engine_gui_compatibility.py::test_default_constructor_preserves_standalone_portrait_options` | 0.217316 | 0.215391 | 0.217962 |
| `tests/gui/test_image_presenter.py::test_update_ignores_stale_engine_callback_for_other_scope` | 0.214397 | 0.206656 | 0.215442 |
| `tests/cli/test_lcs.py::test_host_defaults_to_the_portrait_overlay_geometry` | 0.213458 | 0.213155 | 0.213813 |
| `tests/protocol/sequence/test_speed_ramp.py::TestSpeedRamp::test_an_abort_waits_for_a_step_already_on_the_wire` | 0.201338 | 0.201311 | 0.201374 |
| `tests/utils/test_path_util.py::test_find_installation_dir` | 0.174976 | 0.172528 | 0.175156 |
| `tests/test_pytest.py::TestPyTrain::test_get_version` | 0.119895 | 0.119279 | 0.126643 |
| `tests/gui/test_component_state_gui.py::test_cycle_gui_ignores_unknown_key` | 0.100310 | 0.100251 | 0.100797 |
| `tests/protocol/sequence/test_ramp_peer.py::test_timestamp_race_converges_without_startup_echo[False-False-3180-CommandScope.ENGINE]` | 0.097034 | 0.000887 | 0.106638 |
| `tests/gui/test_route_builder_panel.py::test_picker_size_and_page_navigation_follow_available_layout[480-800-True-linux-330-38]` | 0.083283 | 0.081364 | 0.083361 |
| `tests/gui/test_checkbox_group.py::test_the_cursor_tints_the_row_it_is_moved_to` | 0.071660 | 0.065683 | 0.073078 |
| `tests/cli/test_make_gui.py::test_make_gui_parser_accepts_no_cache_sync` | 0.070352 | 0.070212 | 0.070566 |
| `tests/cli/test_make_service.py::TestMakeService::test_parser` | 0.053672 | 0.053067 | 0.054216 |
| `tests/cli/test_cache_sync_service.py::test_shutdown_cache_retains_manager_on_failure_then_retries[2-KeyboardInterrupt]` | 0.053263 | 0.049828 | 0.054332 |
| `tests/cli/test_make_gui.py::test_other_guis_still_autostart_unconditionally` | 0.051559 | 0.051225 | 0.054969 |
| `tests/protocol/sequence/test_speed_ramp.py::TestSpeedRamp::test_an_abort_stalled_on_the_wire_still_completes` | 0.051432 | 0.050482 | 0.051434 |
| `tests/cli/test_make_gui.py::test_desktop_autostart_abbreviates` | 0.051314 | 0.050541 | 0.051443 |
| `tests/cli/test_make_gui.py::test_make_gui_parser_constructs_landscape_controller` | 0.050358 | 0.049868 | 0.051059 |

## Teardown phases

| Item | Median | Min | Max |
|---|---:|---:|---:|
| `tests/utils/test_wifi_info.py::test_macos_airport_output_is_parsed` | 0.000750 | 0.000670 | 0.000777 |
| `tests/cli/test_pytrain.py::test_parser_rejects_invalid_options[args0]` | 0.000669 | 0.000594 | 0.000704 |
| `tests/cli/test_pytrain.py::test_parser_rejects_invalid_options[args2]` | 0.000667 | 0.000655 | 0.000735 |
| `tests/cli/test_pytrain.py::test_parser_rejects_invalid_options[args4]` | 0.000667 | 0.000582 | 0.000669 |
| `tests/cli/test_pytrain.py::test_parser_rejects_invalid_options[args6]` | 0.000639 | 0.000610 | 0.000763 |
| `tests/cli/test_pytrain.py::test_parser_rejects_invalid_options[args5]` | 0.000636 | 0.000597 | 0.000666 |
| `tests/cli/test_pytrain.py::test_parser_rejects_invalid_options[args1]` | 0.000628 | 0.000589 | 0.000665 |
| `tests/cli/test_pytrain.py::test_parser_rejects_invalid_options[args3]` | 0.000612 | 0.000569 | 0.000669 |
| `tests/cli/test_pytrain.py::test_parser_defaults` | 0.000571 | 0.000546 | 0.000645 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[fork]` | 0.000435 | 0.000386 | 0.000480 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[forkserver]` | 0.000416 | 0.000356 | 0.000433 |
| `tests/cli/test_pytrain_runtime.py::test_interactive_parser_errors_continue[error1]` | 0.000407 | 0.000394 | 0.000460 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[spawn]` | 0.000399 | 0.000333 | 0.000462 |
| `tests/cli/test_pytrain.py::test_server_startup[args0-192.0.2.30-50001-False]` | 0.000383 | 0.000349 | 0.000387 |
| `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath[True]` | 0.000378 | 0.000359 | 0.000384 |
| `tests/utils/test_ip_tools.py::test_get_ip_address_non_linux_retries_until_success` | 0.000364 | 0.000294 | 0.000364 |
| `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath[False]` | 0.000362 | 0.000352 | 0.000398 |
| `tests/cli/test_pytrain_runtime.py::test_unexpected_runtime_errors_still_close_service_and_cache[True-buttons]` | 0.000333 | 0.000210 | 0.000357 |
| `tests/integration/test_pytrain_api_exit.py::test_api_exit_receiver[UPGRADE-queued-server]` | 0.000321 | 0.000315 | 0.000329 |
| `tests/protocol/sequence/test_ramp_peer.py::test_timestamp_race_converges_without_startup_echo[False-False-3180-CommandScope.TRAIN]` | 0.000319 | 0.000273 | 0.000352 |
| `tests/cli/test_pytrain_commands.py::test_quit_routing[False-]` | 0.000312 | 0.000196 | 0.000383 |
| `tests/cli/test_cache_sync_service.py::test_shutdown_cache_retains_manager_on_failure_then_retries[2-KeyboardInterrupt]` | 0.000310 | 0.000298 | 0.000330 |
| `tests/cli/test_pytrain_state.py::test_roster_requests[sync2-True-True]` | 0.000307 | 0.000212 | 0.000315 |
| `tests/test_pytest.py::TestPyTrain::test_get_version` | 0.000301 | 0.000282 | 0.000367 |
| `tests/cli/test_pytrain_commands.py::test_parse_failure_mode_isolation[engine -h-unknown-unrecognized arguments]` | 0.000298 | 0.000266 | 0.000332 |

## Fixture setup totals

Exclusive of dependency setup; includes fixture hook overhead. Finalizers are attributed only to case teardown, not individual fixtures.

| Fixture (source) | Invocations/run | Median total |
|---|---:|---:|
| `panel (tests/gui/test_route_builder_panel.py)` | 317 | 0.661280 |
| `pdi_send (tests/protocol/sequence/conftest.py)` | 859 | 0.283568 |
| `desktop_panel (tests/gui/test_route_builder_panel.py)` | 89 | 0.114041 |
| `runtime (tests/cli/test_pytrain_runtime.py)` | 144 | 0.099772 |
| `tmp_path (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/tmpdir.py)` | 185 | 0.063318 |
| `transport (tests/cli/test_pytrain_pdi.py)` | 140 | 0.054797 |
| `admin (tests/cli/test_pytrain_admin.py)` | 134 | 0.042679 |
| `ramp_target_update (tests/protocol/sequence/conftest.py)` | 131 | 0.033385 |
| `monkeypatch (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/monkeypatch.py)` | 3835 | 0.031493 |
| `deck_picker (tests/gui/test_route_builder_panel.py)` | 53 | 0.029208 |
| `command_train (tests/cli/test_pytrain_commands.py)` | 55 | 0.028359 |
| `pytrain_isolation (tests/cli/conftest.py)` | 667 | 0.028356 |
| `editable_text_module (tests/gui/test_editable_text.py)` | 75 | 0.025018 |
| `pytrain_startup (tests/cli/conftest.py)` | 16 | 0.019676 |
| `state_train (tests/cli/test_pytrain_state.py)` | 46 | 0.019301 |
| `host (tests/gui/test_routes_gui.py)` | 29 | 0.014231 |
| `cache_service (tests/cli/test_cache_sync_service.py)` | 25 | 0.011566 |
| `discovery (tests/cli/test_pytrain_service_discovery.py)` | 21 | 0.011483 |
| `scope (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 976 | 0.011174 |
| `command (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 953 | 0.011164 |
| `pi_panel (tests/gui/test_route_builder_panel.py)` | 6 | 0.011082 |
| `repo_root (tests/cli/test_pytrain_update.py)` | 40 | 0.008669 |
| `_xunit_setup_method_fixture_TestSpeedRampGeometry (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 523 | 0.008441 |
| `address (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 729 | 0.007684 |
| `bare_pytrain (tests/cli/conftest.py)` | 667 | 0.006228 |
| `speed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 538 | 0.005867 |
| `expected (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 483 | 0.004945 |
| `_patch_widgets (tests/gui/test_lcs_config_panel.py)` | 424 | 0.004620 |
| `outbound_speed_lookups (tests/pdi/test_base_req.py)` | 130 | 0.003807 |
| `isolated_state_store (tests/db/test_comp_data.py)` | 361 | 0.003594 |
| `io (tests/db/test_irda_state.py)` | 55 | 0.003517 |
| `mod (tests/gui/test_touch_list_box.py)` | 19 | 0.003483 |
| `caplog (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/logging.py)` | 273 | 0.003410 |
| `state (tests/db/test_ramp_claim_state.py)` | 73 | 0.002860 |
| `config (tests/test_deck_packaging.py)` | 7 | 0.002794 |
| `api_cache_shutdown (tests/cli/test_pytrain_admin.py)` | 8 | 0.002689 |
| `field (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 197 | 0.002472 |
| `native_speed_state (tests/pdi/test_base_req.py)` | 20 | 0.002348 |
| `text (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 185 | 0.002293 |
| `state_lookups (tests/pdi/test_irda_req.py)` | 68 | 0.002237 |
| `already_set (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 140 | 0.002160 |
| `offset (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 223 | 0.002143 |
| `pin_process_globals (tests/db/test_engine_state_core.py)` | 229 | 0.002089 |
| `action (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 179 | 0.002053 |
| `sync_dispatch (tests/pdi/test_base_req.py)` | 48 | 0.001987 |
| `fake_socket (tests/comm/test_comm_buffer_proxy_disconnect.py)` | 7 | 0.001863 |
| `valid1 (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 181 | 0.001794 |
| `bias (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 181 | 0.001779 |
| `capsys (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/capture.py)` | 73 | 0.001762 |
| `valid2 (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 175 | 0.001740 |
| `claimed_update (tests/cli/test_pytrain_update.py)` | 35 | 0.001728 |
| `_xunit_setup_method_fixture_TestCommandReq (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 104 | 0.001682 |
| `name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 133 | 0.001681 |
| `_xunit_setup_method_fixture_TestSpeedRamp (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 84 | 0.001652 |
| `labeled (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.001641 |
| `data (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 155 | 0.001529 |
| `service_failure (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.001512 |
| `compact (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 128 | 0.001511 |
| `is_ramping (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 144 | 0.001503 |
| `_xunit_setup_method_fixture_TestSpeedToRpm (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 88 | 0.001481 |
| `_xunit_setup_method_fixture_TestTwoControllerRamp (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 19 | 0.001471 |
| `build_deck (tests/test_deck_packaging.py)` | 8 | 0.001466 |
| `label (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 159 | 0.001465 |
| `mode (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 141 | 0.001415 |
| `_patch_runtime (tests/gui/test_guizero_base.py)` | 47 | 0.001414 |
| `address_bytes (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 156 | 0.001399 |
| `value (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 102 | 0.001392 |
| `speed_update_lookups (tests/pdi/test_base_req.py)` | 46 | 0.001390 |
| `data_cls (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 117 | 0.001389 |
| `current (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 128 | 0.001335 |
| `target (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 119 | 0.001280 |
| `builder (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 102 | 0.001274 |
| `operation (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 13 | 0.001273 |
| `momentum (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 50 | 0.001250 |
| `target_speed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 134 | 0.001204 |
| `_patch_widgets (tests/gui/test_keypad_view.py)` | 124 | 0.001148 |
| `size (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 80 | 0.001133 |
| `error (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 96 | 0.001081 |
| `enabled (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 68 | 0.001055 |
| `_xunit_setup_method_fixture_TestRampSpeedReq (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 68 | 0.001048 |
| `max_speed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 91 | 0.001022 |
| `horizontal (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 58 | 0.001017 |
| `previous_type (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 72 | 0.001004 |
| `kind (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 77 | 0.001001 |
| `tmcc_id (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 86 | 0.000981 |
| `proxy (tests/comm/test_comm_buffer_proxy_disconnect.py)` | 7 | 0.000969 |
| `_xunit_setup_function_fixture_tests.db.test_prod_info (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000964 |
| `engine_type (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 88 | 0.000939 |
| `api (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 90 | 0.000937 |
| `pin_process_globals (tests/db/test_engine_state.py)` | 95 | 0.000895 |
| `reverse (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 94 | 0.000895 |
| `_xunit_setup_method_fixture_TestComponentState (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 64 | 0.000887 |
| `width (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 62 | 0.000884 |
| `stage (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 61 | 0.000841 |
| `delta (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 57 | 0.000791 |
| `lifecycle (tests/db/test_cache_sync.py)` | 14 | 0.000772 |
| `sensor (tests/db/test_irda_state.py)` | 53 | 0.000763 |
| `_no_display (tests/gui/test_checkbox_group.py)` | 113 | 0.000761 |
| `raw (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 52 | 0.000723 |
| `dx (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 62 | 0.000698 |
| `is_legacy (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 65 | 0.000672 |
| `args (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 46 | 0.000651 |
| `pytrain (tests/cli/test_routes.py)` | 24 | 0.000634 |
| `pending (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 54 | 0.000631 |
| `flags (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 47 | 0.000626 |
| `use_factory (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 72 | 0.000625 |
| `clean_logging (tests/utils/test_dual_logging.py)` | 10 | 0.000608 |
| `dy (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 62 | 0.000603 |
| `no_comm_buffer (tests/db/test_engine_state.py)` | 74 | 0.000593 |
| `mock_comm_external_io (tests/comm/conftest.py)` | 1 | 0.000585 |
| `sequence (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 45 | 0.000578 |
| `sandbox (tests/test_deck_packaging.py)` | 4 | 0.000577 |
| `timestamp_ms (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 60 | 0.000576 |
| `_xunit_setup_method_fixture_TestRampArbitration (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 36 | 0.000567 |
| `cmd_line (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 42 | 0.000554 |
| `run_before_and_after_tests (tests/db/test_component_state.py)` | 64 | 0.000553 |
| `_patch_widgets (tests/gui/test_gui_checkpoint.py)` | 64 | 0.000536 |
| `packet (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 26 | 0.000534 |
| `real_exit_runtime (tests/cli/test_pytrain_runtime.py)` | 4 | 0.000532 |
| `mutation (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 52 | 0.000532 |
| `code (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 43 | 0.000523 |
| `panel (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 27 | 0.000513 |
| `from_tmcc_rx (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 32 | 0.000502 |
| `entry_point (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 52 | 0.000501 |
| `filter_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 36 | 0.000497 |
| `port (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 29 | 0.000491 |
| `_no_display (tests/gui/test_scroll_box.py)` | 61 | 0.000469 |
| `_patch_widgets (tests/gui/test_gui_deck_parity.py)` | 52 | 0.000459 |
| `length (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 38 | 0.000459 |
| `location (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000457 |
| `packaged (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000456 |
| `is_package (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 39 | 0.000450 |
| `initialized_update_state (tests/pdi/test_base_req.py)` | 44 | 0.000450 |
| `reset_singletons (tests/db/test_component_state_store_ai.py)` | 44 | 0.000449 |
| `dispatcher (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000445 |
| `unsafe_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000441 |
| `prop (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 39 | 0.000441 |
| `digit (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 33 | 0.000436 |
| `_xunit_setup_method_fixture_TestCommandDispatcher (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 28 | 0.000429 |
| `legacy (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 36 | 0.000419 |
| `signed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 46 | 0.000417 |
| `_xunit_setup_method_fixture_TestEchoLedger (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 27 | 0.000407 |
| `context (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 31 | 0.000391 |
| `is_rx (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 32 | 0.000380 |
| `payload (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 29 | 0.000370 |
| `expected_momentum (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000367 |
| `launcher_factory (tests/cli/test_make_gui.py)` | 4 | 0.000362 |
| `editor (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 30 | 0.000352 |
| `verb (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 36 | 0.000352 |
| `engine_id (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 27 | 0.000351 |
| `wait_command (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 35 | 0.000349 |
| `smoke (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 33 | 0.000348 |
| `gui_class (tests/cli/test_routes.py)` | 19 | 0.000345 |
| `height (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 31 | 0.000341 |
| `system (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 26 | 0.000341 |
| `platform (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 24 | 0.000324 |
| `bundled_font (tests/gui/test_bundled_fonts.py)` | 12 | 0.000320 |
| `linux (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 27 | 0.000317 |
| `touch_list (tests/gui/test_touch_list.py)` | 9 | 0.000311 |
| `status (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 26 | 0.000308 |
| `feature (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 28 | 0.000306 |
| `server (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 23 | 0.000304 |
| `control_type (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 25 | 0.000296 |
| `run_before_and_after_tests (tests/comm/test_dispatch_listener.py)` | 28 | 0.000294 |
| `direction (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 27 | 0.000290 |
| `bit (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 24 | 0.000286 |
| `button (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 27 | 0.000283 |
| `host (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 23 | 0.000283 |
| `patch_guizero_and_system (tests/gui/test_dummy_gui_components.py)` | 6 | 0.000280 |
| `peers (tests/protocol/sequence/test_ramp_peer.py)` | 32 | 0.000274 |
| `late_action (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 30 | 0.000272 |
| `initial (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 28 | 0.000265 |
| `data_bytes (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000264 |
| `failure (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 21 | 0.000262 |
| `unavailable (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 17 | 0.000261 |
| `instance (tests/gui/test_dummy_gui_components.py)` | 1 | 0.000260 |
| `style (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 26 | 0.000258 |
| `attribute (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 25 | 0.000258 |
| `_xunit_setup_method_fixture_TestRampRegistry (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000257 |
| `desktop (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 18 | 0.000255 |
| `engine_states (tests/protocol/sequence/test_ramp_peer.py)` | 23 | 0.000250 |
| `send_request (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 28 | 0.000246 |
| `module (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 18 | 0.000245 |
| `mock_network_wait (tests/utils/test_ip_tools.py)` | 22 | 0.000241 |
| `position (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 24 | 0.000231 |
| `stop (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 16 | 0.000227 |
| `inherited (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000226 |
| `tmcc_speed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000221 |
| `one_process (tests/protocol/sequence/test_two_controller_ramp.py)` | 19 | 0.000220 |
| `headless (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 21 | 0.000220 |
| `no_wait (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 21 | 0.000217 |
| `tmcc_target (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 24 | 0.000214 |
| `raw_target (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 24 | 0.000210 |
| `module_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000209 |
| `chain (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 16 | 0.000205 |
| `road_number (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 18 | 0.000205 |
| `commands (tests/cli/test_pytrain_update.py)` | 25 | 0.000200 |
| `sync (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 21 | 0.000198 |
| `key (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 17 | 0.000196 |
| `level (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000196 |
| `encoded (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 22 | 0.000194 |
| `tag (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 15 | 0.000192 |
| `state_cls (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 19 | 0.000191 |
| `needs (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000191 |
| `device (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000188 |
| `tmcc_packets (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000187 |
| `properties (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 17 | 0.000186 |
| `as_action (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000185 |
| `method (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 16 | 0.000185 |
| `cache_failure (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 17 | 0.000184 |
| `units (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000184 |
| `_patch_runtime (tests/cli/test_lcs.py)` | 13 | 0.000182 |
| `rpm (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 16 | 0.000182 |
| `button_size (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000182 |
| `parts (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000181 |
| `train_id (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 18 | 0.000179 |
| `legacy_speed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000177 |
| `mac_platform (tests/gui/test_swipe_detector.py)` | 25 | 0.000176 |
| `legacy_packets (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000174 |
| `index (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000173 |
| `_xunit_setup_method_fixture_TestConstants (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000173 |
| `on (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 18 | 0.000168 |
| `road_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000164 |
| `policy (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000162 |
| `state (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000160 |
| `error_type (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000160 |
| `show_unlabeled (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000158 |
| `parent (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000158 |
| `unmeasured (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000157 |
| `reg (tests/gui/accessory/test_accessory_registry.py)` | 7 | 0.000156 |
| `no_thread_start (tests/db/test_startup_state.py)` | 9 | 0.000153 |
| `action_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000151 |
| `scrolls (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 16 | 0.000149 |
| `source (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 11 | 0.000148 |
| `destination (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 16 | 0.000146 |
| `build_component_store (tests/db/test_startup_state.py)` | 9 | 0.000146 |
| `parsed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 16 | 0.000143 |
| `catalog (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 16 | 0.000141 |
| `_patch_widgets (tests/gui/test_motors_gui.py)` | 17 | 0.000140 |
| `available (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 15 | 0.000139 |
| `brake (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000138 |
| `same_millisecond (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 16 | 0.000138 |
| `returncode (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000137 |
| `ramp_status (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000137 |
| `invalid (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000136 |
| `suffix (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000136 |
| `reset_singleton (tests/comm/test_enqueue_proxy_requests.py)` | 16 | 0.000136 |
| `leading_rx (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000132 |
| `family (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000132 |
| `budget (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000132 |
| `is_cab1 (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 13 | 0.000129 |
| `refresh (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000128 |
| `number (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 11 | 0.000128 |
| `sort (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000127 |
| `platform_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000126 |
| `startup (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000126 |
| `failure_point (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000126 |
| `include_state (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000125 |
| `start (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 11 | 0.000124 |
| `_patch_widgets (tests/gui/test_amc2_ops_panel.py)` | 14 | 0.000123 |
| `reading (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000122 |
| `device_key (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000119 |
| `expected_brake (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000118 |
| `_xunit_setup_method_fixture_TestEchoFamily (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000117 |
| `options (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000117 |
| `values (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000114 |
| `search (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000114 |
| `result (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 11 | 0.000113 |
| `expected_scope (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 11 | 0.000113 |
| `use_subclass (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000113 |
| `rate (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000112 |
| `patched_engine_status (tests/gpio/test_engine_status.py)` | 4 | 0.000111 |
| `requested_speed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000110 |
| `enum_cls (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000109 |
| `alias (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000109 |
| `request_type (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000109 |
| `flag (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000107 |
| `cls (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000106 |
| `deck (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000106 |
| `protocol (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000105 |
| `event (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000105 |
| `engine_packet (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000105 |
| `train_packet (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000101 |
| `expected_start (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000100 |
| `class_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000098 |
| `side (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000098 |
| `is_forward (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000097 |
| `title (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000094 |
| `root_at_info (tests/cli/test_pytrain_service_discovery.py)` | 4 | 0.000093 |
| `claim_id (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000092 |
| `refresh_before_release (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000092 |
| `patch_gui_classes (tests/gui/test_component_state_gui.py)` | 7 | 0.000091 |
| `rows (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000090 |
| `_patch_registry_and_catalog (tests/gui/accessory/test_accessory_gui.py)` | 10 | 0.000090 |
| `bluetooth_id (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000090 |
| `asked (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000090 |
| `is_server (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000090 |
| `_isolate (tests/gui/accessory/test_accessory_gui.py)` | 10 | 0.000090 |
| `_xunit_setup_method_fixture_TestBlock (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000089 |
| `_xunit_setup_method_fixture_TestPyTrain (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000089 |
| `pane (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000088 |
| `req_cls (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000088 |
| `cmd_enum (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000087 |
| `query (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000087 |
| `user_defined (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000087 |
| `mode_key (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000085 |
| `is_reverse (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000085 |
| `title_overhead (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000085 |
| `descending (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000084 |
| `popup_visible (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000084 |
| `engine_target (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000084 |
| `thru (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000082 |
| `initialized (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000081 |
| `_xunit_setup_method_fixture_TestCommandListener (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000081 |
| `original (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000081 |
| `debug (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000081 |
| `expected_base (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000079 |
| `present (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000079 |
| `is_d4 (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000079 |
| `known_server (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000078 |
| `include_lcs (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000078 |
| `_patch_classes (tests/gui/test_wide_component_state_gui.py)` | 6 | 0.000078 |
| `addresses (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000077 |
| `found (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000077 |
| `release (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000077 |
| `event_type (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000075 |
| `gui_class (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000075 |
| `comp_data (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000075 |
| `ident (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000075 |
| `discovers (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000074 |
| `route (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000074 |
| `percentage (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000073 |
| `base (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000072 |
| `resolved_id (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000072 |
| `enter_key (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000072 |
| `clear_info (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000071 |
| `_xunit_setup_method_fixture_TestI2c (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000070 |
| `expected_id (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000070 |
| `is_api (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000070 |
| `reset_singleton_state (tests/db/test_client_state_listener.py)` | 9 | 0.000069 |
| `capable (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000069 |
| `replacement (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000069 |
| `remainder (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000068 |
| `params (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000067 |
| `header_height (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000066 |
| `tmcc (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000063 |
| `clean_singletons (tests/pdi/test_pdi_listener.py)` | 6 | 0.000063 |
| `version (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000063 |
| `has_address (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000063 |
| `expected_height (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000061 |
| `styled (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000061 |
| `sort_order (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000061 |
| `details (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000061 |
| `show_keyboard (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000061 |
| `count (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000060 |
| `extra (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000060 |
| `buttons (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000060 |
| `bar_width (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000059 |
| `refusal (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000058 |
| `existing (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000058 |
| `owned_thread (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000058 |
| `diagnostic (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000058 |
| `moved (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000057 |
| `kwargs (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000057 |
| `foreign (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000056 |
| `y (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000056 |
| `notches (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000056 |
| `fake_time (tests/utils/test_expiring_set.py)` | 7 | 0.000056 |
| `missing (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000055 |
| `clean_singletons (tests/pdi/test_base3_buffer.py)` | 6 | 0.000055 |
| `run_before_and_after_tests (tests/comm/test_command_listener.py)` | 4 | 0.000054 |
| `success (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000053 |
| `first_command (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000053 |
| `scale_by (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000053 |
| `help_text (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000053 |
| `real (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000053 |
| `from_root (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000053 |
| `speed_limit (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000052 |
| `reset_listener_singleton (tests/comm/test_command_listener_ai.py)` | 5 | 0.000052 |
| `hostname (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000052 |
| `widget_factory (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000052 |
| `second_button (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000052 |
| `do_async (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000052 |
| `px_per_char (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000051 |
| `state_type (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000051 |
| `motor1_restore (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000051 |
| `spare (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000051 |
| `pad_x (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000051 |
| `digit_count (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000051 |
| `queue_present (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000051 |
| `pad_y (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000051 |
| `hat (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000049 |
| `wide (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000049 |
| `cramped (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000049 |
| `same_host (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000048 |
| `reset_singletons (tests/pdi/test_base3_buffer.py)` | 3 | 0.000048 |
| `gap (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000048 |
| `reboot (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000047 |
| `expected_defaults (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000047 |
| `service (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000047 |
| `interrupt (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000047 |
| `unsafe_path (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000047 |
| `echo_error (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000046 |
| `soft_status (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000046 |
| `is_base (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000046 |
| `exception (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000045 |
| `package (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000045 |
| `selected (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000044 |
| `speeds (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000044 |
| `pdi (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000044 |
| `missing_native (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000044 |
| `loco_id (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000043 |
| `font_size (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000043 |
| `state_kind (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000043 |
| `failures (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000043 |
| `claimed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000043 |
| `lcs_req (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000042 |
| `queue (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000042 |
| `stand_alone (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000041 |
| `motor2_restore (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000041 |
| `script (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000041 |
| `manager (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000041 |
| `as_request (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000041 |
| `output_type (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000041 |
| `root_at_info (tests/cli/test_pytrain_debug_toggle.py)` | 2 | 0.000041 |
| `base_id (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000041 |
| `info (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000040 |
| `held_before_claim (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000040 |
| `skipped (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000040 |
| `connection (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000039 |
| `is_ser2 (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000039 |
| `expected_pdi_command (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000039 |
| `extended (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000039 |
| `pending_step (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000039 |
| `callback_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000039 |
| `reset_singleton (tests/pdi/test_pdi_state_store.py)` | 4 | 0.000039 |
| `from_ops (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000039 |
| `sort_key (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000038 |
| `report (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000038 |
| `age (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000038 |
| `below (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000037 |
| `role (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000037 |
| `loco_rl (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000036 |
| `thread (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000036 |
| `_patch_panel (tests/gui/test_lcs_panel_wiring.py)` | 4 | 0.000036 |
| `ser2 (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000035 |
| `config (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000035 |
| `num_ids (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000035 |
| `components (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000035 |
| `owns_window (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000035 |
| `remote (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000034 |
| `allow (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000034 |
| `back_reference (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000034 |
| `required_height (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000033 |
| `parent_gui (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000033 |
| `indirect (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000032 |
| `guid (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000031 |
| `zeroconf (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000031 |
| `settling (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000031 |
| `scale (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000031 |
| `field_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000031 |
| `loco_lr (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000031 |
| `synchronized (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000030 |
| `discard_focused (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000030 |
| `echo (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000030 |
| `cleared (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000030 |
| `retry_interrupted (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000030 |
| `cancel_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000029 |
| `is_tmcc (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000029 |
| `explicit (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000028 |
| `left_to_right (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000028 |
| `row (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000028 |
| `right_to_left (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000028 |
| `mock_pdi_dispatcher_ip (tests/pdi/conftest.py)` | 1 | 0.000028 |
| `exists (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000028 |
| `windowing_system (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000028 |
| `controller_view (tests/gui/test_controller_view.py)` | 1 | 0.000028 |
| `view (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000028 |
| `controller (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000027 |
| `updates (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000027 |
| `payload_type (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000027 |
| `header_available (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000027 |
| `expected_rl (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000027 |
| `tick_before_claim (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000027 |
| `expected_lr (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000027 |
| `_unittest_setUpClass_fixture_TestMCP23017 (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/unittest.py)` | 1 | 0.000026 |
| `native (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000026 |
| `do_fire (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000026 |
| `state_change (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000026 |
| `released (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000026 |
| `prefix (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000025 |
| `yes_focused (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000025 |
| `restore (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000025 |
| `canceled (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000025 |
| `preferred (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000025 |
| `pressed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000025 |
| `state_class (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000025 |
| `supported (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000025 |
| `panel_kind (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000024 |
| `relaunch (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000024 |
| `acquired (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000024 |
| `pdi_command (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000024 |
| `minimum (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000024 |
| `managed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000024 |
| `border_thickness (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000024 |
| `touch (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000023 |
| `owns_ramp (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000023 |
| `held (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000023 |
| `cancel_button (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000023 |
| `tmp_path_factory (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/tmpdir.py)` | 1 | 0.000023 |
| `dependency (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000023 |
| `stretch (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000023 |
| `option_pad (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000023 |
| `takeover_speed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000023 |
| `large (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000023 |
| `controlled_keepalive (tests/pdi/test_base3_buffer.py)` | 2 | 0.000023 |
| `expected_payload (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000023 |
| `row_height (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000022 |
| `has_manager (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000022 |
| `parse_only (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000021 |
| `server_version (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000021 |
| `heading (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000021 |
| `exit_code (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000021 |
| `backend (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000020 |
| `_xunit_setup_method_fixture_TestMakeService (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 1 | 0.000020 |
| `parent_width (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000020 |
| `registered (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000020 |
| `load_bundled (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000020 |
| `section (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000020 |
| `stdout (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000019 |
| `mock_command_dispatcher_ip (tests/db/conftest.py)` | 1 | 0.000019 |
| `_xunit_setup_method_fixture_TestComponentStateStore (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 1 | 0.000018 |
| `_unittest_setUpClass_fixture_TestGPIODevice (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/unittest.py)` | 1 | 0.000018 |
| `page (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000018 |
| `ceiling (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000018 |
| `on_screen (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000018 |
| `note_pad (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000018 |
| `id_page (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000017 |
| `echo_packet (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000017 |
| `sent_packet (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000017 |
| `prose (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000017 |
| `_xunit_setup_method_fixture_TestEngineStateRoutesThroughTheRegistry (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 1 | 0.000016 |
| `_unittest_setup_method_fixture_TestGPIODevice (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/unittest.py)` | 1 | 0.000014 |
| `run_before_and_after_tests (tests/db/test_component_state_store.py)` | 1 | 0.000014 |
