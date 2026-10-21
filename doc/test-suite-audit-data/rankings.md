# Measured rankings

Seconds; median across three runs. Module/family totals include setup, call, and teardown.

## Individual phases

| Item | Median | Min | Max |
|---|---:|---:|---:|
| `tests/cli/test_make_service.py::TestMakeService::test_parser (call)` | 0.772910 | 0.763090 | 0.803333 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[spawn] (call)` | 0.590079 | 0.581747 | 0.604475 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[forkserver] (call)` | 0.568693 | 0.563936 | 0.587465 |
| `tests/db/test_cache_sync.py::test_stop_without_listener_terminates_real_worker (call)` | 0.504494 | 0.502071 | 0.505771 |
| `tests/cli/test_make_service.py::test_make_service_shell_script_includes_cache_sync_switch_only_when_disabled (call)` | 0.417321 | 0.403607 | 0.448490 |
| `tests/cli/test_make_gui.py::test_make_gui_shell_script_includes_cache_sync_switch_only_when_disabled (call)` | 0.398750 | 0.386867 | 0.410166 |
| `tests/gui/controller/test_controls_panel.py::test_a_measured_ruler_reports_the_font_tk_will_draw_in (call)` | 0.338288 | 0.329269 | 0.367792 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[fork] (call)` | 0.312380 | 0.300541 | 0.313998 |
| `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath[False] (call)` | 0.303646 | 0.300348 | 0.307578 |
| `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath[True] (call)` | 0.296392 | 0.290709 | 0.299295 |
| `tests/gui/test_route_builder_panel.py::test_successful_clear_hides_panel_through_popup_manager (call)` | 0.214796 | 0.208822 | 0.215660 |
| `tests/gui/controller/test_engine_gui_compatibility.py::test_default_constructor_preserves_standalone_portrait_options (call)` | 0.212558 | 0.210674 | 0.219088 |
| `tests/cli/test_lcs.py::test_host_defaults_to_the_portrait_overlay_geometry (call)` | 0.210226 | 0.203082 | 0.304830 |
| `tests/protocol/sequence/test_speed_ramp.py::TestSpeedRamp::test_an_abort_waits_for_a_step_already_on_the_wire (call)` | 0.200595 | 0.200491 | 0.201449 |
| `tests/gui/test_image_presenter.py::test_update_ignores_stale_engine_callback_for_other_scope (call)` | 0.200421 | 0.199913 | 0.220683 |
| `tests/cli/test_make_gui.py::test_shell_script_exports_the_platform_it_was_generated_for[SteamDeckGui-steamdeck] (call)` | 0.198665 | 0.195780 | 0.198991 |
| `tests/cli/test_make_gui.py::test_shell_script_exports_the_platform_it_was_generated_for[EngineGui-] (call)` | 0.196624 | 0.194713 | 0.197019 |
| `tests/utils/test_path_util.py::test_find_installation_dir (call)` | 0.166095 | 0.165729 | 0.169686 |
| `tests/test_pytest.py::TestPyTrain::test_get_version (call)` | 0.119413 | 0.118058 | 0.123008 |
| `tests/gui/test_component_state_gui.py::test_cycle_gui_ignores_unknown_key (call)` | 0.101269 | 0.100833 | 0.101359 |
| `tests/gui/test_route_builder_panel.py::test_desktop_wheel_browses_both_lists[win32--1-1-False] (setup)` | 0.096113 | 0.003041 | 0.104679 |
| `tests/gui/test_route_builder_panel.py::test_pi_button_resize_ignores_unavailable_editor_geometry[destroyed] (setup)` | 0.094879 | 0.003192 | 0.102020 |
| `tests/gui/test_touch_list_box.py::test_precise_horizontal_scroll_obeys_policy[True] (setup)` | 0.093929 | 0.000306 | 0.111666 |
| `tests/gui/test_route_builder_panel.py::test_deck_picker_search_editing_blocks_selection_but_allows_cancel_and_halt[dpad_left-None] (setup)` | 0.084379 | 0.001992 | 0.088076 |
| `tests/cli/test_make_gui.py::test_make_gui_parser_accepts_no_cache_sync (call)` | 0.072088 | 0.068216 | 0.078287 |

## Individual cases

| Item | Median | Min | Max |
|---|---:|---:|---:|
| `tests/cli/test_make_service.py::TestMakeService::test_parser` | 0.773499 | 0.763511 | 0.803714 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[spawn]` | 0.591586 | 0.583101 | 0.606064 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[forkserver]` | 0.570137 | 0.565373 | 0.588885 |
| `tests/db/test_cache_sync.py::test_stop_without_listener_terminates_real_worker` | 0.504969 | 0.502568 | 0.506243 |
| `tests/cli/test_make_service.py::test_make_service_shell_script_includes_cache_sync_switch_only_when_disabled` | 0.418066 | 0.404278 | 0.449158 |
| `tests/cli/test_make_gui.py::test_make_gui_shell_script_includes_cache_sync_switch_only_when_disabled` | 0.399503 | 0.387613 | 0.410895 |
| `tests/gui/controller/test_controls_panel.py::test_a_measured_ruler_reports_the_font_tk_will_draw_in` | 0.338461 | 0.329431 | 0.367955 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[fork]` | 0.313406 | 0.301662 | 0.315205 |
| `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath[False]` | 0.304410 | 0.301101 | 0.308371 |
| `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath[True]` | 0.297644 | 0.291891 | 0.300699 |
| `tests/gui/test_route_builder_panel.py::test_successful_clear_hides_panel_through_popup_manager` | 0.216654 | 0.210299 | 0.217361 |
| `tests/gui/controller/test_engine_gui_compatibility.py::test_default_constructor_preserves_standalone_portrait_options` | 0.212749 | 0.210887 | 0.219286 |
| `tests/cli/test_lcs.py::test_host_defaults_to_the_portrait_overlay_geometry` | 0.210721 | 0.203553 | 0.305054 |
| `tests/protocol/sequence/test_speed_ramp.py::TestSpeedRamp::test_an_abort_waits_for_a_step_already_on_the_wire` | 0.201414 | 0.201408 | 0.202668 |
| `tests/gui/test_image_presenter.py::test_update_ignores_stale_engine_callback_for_other_scope` | 0.200611 | 0.200136 | 0.220878 |
| `tests/cli/test_make_gui.py::test_shell_script_exports_the_platform_it_was_generated_for[SteamDeckGui-steamdeck]` | 0.199279 | 0.196286 | 0.199636 |
| `tests/cli/test_make_gui.py::test_shell_script_exports_the_platform_it_was_generated_for[EngineGui-]` | 0.197265 | 0.195482 | 0.197772 |
| `tests/utils/test_path_util.py::test_find_installation_dir` | 0.166351 | 0.165921 | 0.169882 |
| `tests/test_pytest.py::TestPyTrain::test_get_version` | 0.119881 | 0.118568 | 0.123467 |
| `tests/gui/test_component_state_gui.py::test_cycle_gui_ignores_unknown_key` | 0.101518 | 0.101083 | 0.101645 |
| `tests/gui/test_route_builder_panel.py::test_desktop_wheel_browses_both_lists[win32--1-1-False]` | 0.096390 | 0.003256 | 0.105038 |
| `tests/gui/test_route_builder_panel.py::test_pi_button_resize_ignores_unavailable_editor_geometry[destroyed]` | 0.095100 | 0.003356 | 0.102254 |
| `tests/gui/test_touch_list_box.py::test_precise_horizontal_scroll_obeys_policy[True]` | 0.094360 | 0.000466 | 0.111990 |
| `tests/gui/test_route_builder_panel.py::test_deck_picker_search_editing_blocks_selection_but_allows_cancel_and_halt[dpad_left-None]` | 0.084717 | 0.002214 | 0.088425 |
| `tests/cli/test_make_gui.py::test_make_gui_parser_accepts_no_cache_sync` | 0.072503 | 0.068555 | 0.078630 |

## Modules

| Item | Median | Min | Max |
|---|---:|---:|---:|
| `tests/utils/test_logging_multiprocessing.py` | 1.472164 | 1.454899 | 1.508355 |
| `tests/gui/test_route_builder_panel.py` | 1.406765 | 1.404680 | 1.424406 |
| `tests/cli/test_make_service.py` | 1.181956 | 1.178201 | 1.253285 |
| `tests/cli/test_make_gui.py` | 1.144112 | 1.123978 | 1.144442 |
| `tests/cli/test_routes.py` | 0.626315 | 0.624976 | 0.638584 |
| `tests/db/test_cache_sync.py` | 0.573376 | 0.570620 | 0.573410 |
| `tests/cli/test_pytrain.py` | 0.455150 | 0.445666 | 0.480046 |
| `tests/gui/controller/test_controls_panel.py` | 0.415468 | 0.406505 | 0.445815 |
| `tests/protocol/sequence/test_speed_ramp_geometry.py` | 0.391573 | 0.378169 | 0.396073 |
| `tests/protocol/sequence/test_speed_ramp.py` | 0.379847 | 0.363934 | 0.381900 |
| `tests/gui/test_lcs_config_panel.py` | 0.300356 | 0.292196 | 0.322900 |
| `tests/protocol/multibyte/test_ramp_command_req.py` | 0.266975 | 0.262855 | 0.277917 |
| `tests/cli/test_pytrain_runtime.py` | 0.241376 | 0.228900 | 0.242287 |
| `tests/gui/controller/test_engine_gui_compatibility.py` | 0.238234 | 0.229144 | 0.298078 |
| `tests/cli/test_lcs.py` | 0.222950 | 0.214118 | 0.316029 |
| `tests/gui/test_image_presenter.py` | 0.202364 | 0.202060 | 0.223290 |
| `tests/db/test_comp_data.py` | 0.181984 | 0.181030 | 0.194768 |
| `tests/utils/test_path_util.py` | 0.174651 | 0.173737 | 0.177782 |
| `tests/protocol/test_command_req.py` | 0.166468 | 0.164770 | 0.167243 |
| `tests/pdi/test_base_req.py` | 0.161472 | 0.156852 | 0.249608 |
| `tests/gui/controller/test_steam_deck_input.py` | 0.145110 | 0.142392 | 0.145932 |
| `tests/cli/test_pytrain_commands.py` | 0.140920 | 0.135217 | 0.142501 |
| `tests/cli/test_pytrain_pdi.py` | 0.140886 | 0.134237 | 0.144069 |
| `tests/gui/test_component_state_gui.py` | 0.137130 | 0.136546 | 0.137764 |
| `tests/protocol/test_speed_to_rpm.py` | 0.123444 | 0.121055 | 0.126700 |
| `tests/test_pytest.py` | 0.120539 | 0.119304 | 0.124448 |
| `tests/cli/test_pytrain_admin.py` | 0.117892 | 0.117470 | 0.123563 |
| `tests/gui/test_touch_list_box.py` | 0.102194 | 0.007891 | 0.119937 |
| `tests/gui/test_routes_gui.py` | 0.097598 | 0.096071 | 0.108228 |
| `tests/db/test_engine_state_core.py` | 0.085080 | 0.082758 | 0.085085 |
| `tests/cli/test_cache_sync_service.py` | 0.079910 | 0.072487 | 0.080528 |
| `tests/protocol/sequence/test_ramp_peer.py` | 0.072190 | 0.069059 | 0.073319 |
| `tests/utils/test_path_utils.py` | 0.068164 | 0.066864 | 0.068330 |
| `tests/cli/test_pytrain_state.py` | 0.067845 | 0.063598 | 0.067882 |
| `tests/gui/controller/test_engine_gui_conf_import.py` | 0.067424 | 0.001640 | 0.075245 |
| `tests/cli/test_pytrain_service_discovery.py` | 0.062761 | 0.059246 | 0.065934 |
| `tests/comm/test_command_listener_ai.py` | 0.062348 | 0.061975 | 0.065770 |
| `tests/protocol/sequence/test_ramp_speed_req.py` | 0.062269 | 0.060315 | 0.065014 |
| `tests/comm/test_dispatch_listener.py` | 0.060149 | 0.057687 | 0.062182 |
| `tests/gui/test_controller_view.py` | 0.059965 | 0.052655 | 0.063408 |
| `tests/cli/test_pytrain_update.py` | 0.057086 | 0.056947 | 0.059189 |
| `tests/protocol/sequence/test_speed_ramp_echoes.py` | 0.055273 | 0.053234 | 0.058775 |
| `tests/protocol/sequence/test_two_controller_ramp.py` | 0.054194 | 0.051755 | 0.054588 |
| `tests/gui/test_editable_text.py` | 0.052991 | 0.051770 | 0.056314 |
| `tests/db/test_component_state.py` | 0.052487 | 0.051893 | 0.056827 |
| `tests/gui/test_keypad_view.py` | 0.051193 | 0.050846 | 0.056634 |
| `tests/db/test_engine_state.py` | 0.047247 | 0.043818 | 0.047817 |
| `tests/db/test_prod_info.py` | 0.041003 | 0.039941 | 0.041510 |
| `tests/db/test_ramp_claim_state.py` | 0.040674 | 0.039875 | 0.042936 |
| `tests/pdi/test_irda_req.py` | 0.039586 | 0.038907 | 0.041573 |
| `tests/db/test_irda_state.py` | 0.034955 | 0.034838 | 0.034968 |
| `tests/gui/controller/test_accessory_bindings.py` | 0.034838 | 0.034786 | 0.036071 |
| `tests/gui/test_checkbox_group.py` | 0.033956 | 0.033869 | 0.035599 |
| `tests/gui/test_guizero_base.py` | 0.032491 | 0.031771 | 0.033197 |
| `tests/utils/test_ip_tools.py` | 0.030056 | 0.028570 | 0.030316 |
| `tests/gui/test_gui_checkpoint.py` | 0.026827 | 0.026150 | 0.026910 |
| `tests/protocol/sequence/test_ramp_residuals.py` | 0.026463 | 0.026072 | 0.026998 |
| `tests/protocol/multibyte/test_ramp_listener.py` | 0.025295 | 0.024544 | 0.026037 |
| `tests/gui/test_gui_deck_parity.py` | 0.024056 | 0.023999 | 0.024964 |
| `tests/gui/test_route_draft.py` | 0.023508 | 0.021966 | 0.024956 |
| `tests/db/test_component_state_store_ai.py` | 0.022468 | 0.022051 | 0.022986 |
| `tests/gui/controller/test_controller_view_throttle.py` | 0.022311 | 0.022183 | 0.022547 |
| `tests/cli/test_pycab.py` | 0.021600 | 0.020494 | 0.021897 |
| `tests/cli/test_configure.py` | 0.019376 | 0.018618 | 0.020431 |
| `tests/gui/test_steam_deck_gui.py` | 0.019269 | 0.017831 | 0.022425 |
| `tests/test_deck_packaging.py` | 0.019043 | 0.018752 | 0.019579 |
| `tests/gui/controller/test_control_labels.py` | 0.017807 | 0.017694 | 0.017815 |
| `tests/cli/test_pytrain_debug_toggle.py` | 0.017426 | 0.016209 | 0.018967 |
| `tests/gui/test_lcs_device_registry.py` | 0.016901 | 0.016400 | 0.019080 |
| `tests/gui/test_engine_gui_accessories.py` | 0.016209 | 0.015553 | 0.017859 |
| `tests/protocol/sequence/test_ramp_registry.py` | 0.015563 | 0.014339 | 0.016647 |
| `tests/gui/test_engine_gui_create.py` | 0.015519 | 0.015185 | 0.015619 |
| `tests/gui/test_scroll_box.py` | 0.015177 | 0.015089 | 0.016727 |
| `tests/gui/controller/test_popup_manager_compatibility.py` | 0.014774 | 0.014536 | 0.015028 |
| `tests/gui/test_hold_button.py` | 0.013058 | 0.012363 | 0.013229 |
| `tests/comm/test_comm_buffer_proxy_disconnect.py` | 0.013036 | 0.012998 | 0.013241 |
| `tests/gui/controller/test_admin_panel_layout.py` | 0.012194 | 0.012156 | 0.012644 |
| `tests/gui/test_lcs_id_map.py` | 0.011483 | 0.011131 | 0.013927 |
| `tests/gui/test_lcs_imports.py` | 0.011386 | 0.010958 | 0.011698 |
| `tests/gui/test_lcs_sequence_builder.py` | 0.011264 | 0.011078 | 0.012230 |
| `tests/gui/test_bundled_fonts.py` | 0.011061 | 0.010929 | 0.011219 |
| `tests/gui/accessory/test_accessory_gui.py` | 0.010217 | 0.010127 | 0.011357 |
| `tests/utils/test_dual_logging.py` | 0.009591 | 0.009402 | 0.009600 |
| `tests/gui/test_swipe_detector.py` | 0.007691 | 0.007574 | 0.007943 |
| `tests/db/test_components.py` | 0.007681 | 0.007531 | 0.008501 |
| `tests/db/test_lcs_state_serialization.py` | 0.007232 | 0.006898 | 0.007746 |
| `tests/utils/test_image_utils.py` | 0.007117 | 0.006602 | 0.007316 |
| `tests/gui/test_scroll_input.py` | 0.006772 | 0.006335 | 0.007390 |
| `tests/gui/test_pycab_app.py` | 0.006664 | 0.006402 | 0.007422 |
| `tests/gui/test_motors_gui.py` | 0.006418 | 0.005695 | 0.007197 |
| `tests/gui/test_engine_gui_transitions.py` | 0.006200 | 0.006050 | 0.006251 |
| `tests/db/test_component_state_store.py` | 0.006054 | 0.005951 | 0.006360 |
| `tests/comm/test_command_listener.py` | 0.005225 | 0.005144 | 0.006873 |
| `tests/db/test_accessory_state.py` | 0.005034 | 0.004881 | 0.005098 |
| `tests/protocol/test_tmcc1_acc_aux_numbers.py` | 0.004945 | 0.004356 | 0.005119 |
| `tests/gui/test_amc2_ops_panel.py` | 0.004781 | 0.004493 | 0.004801 |
| `tests/comm/test_enqueue_proxy_requests.py` | 0.004578 | 0.004409 | 0.004815 |
| `tests/db/test_startup_state.py` | 0.004558 | 0.004359 | 0.004713 |
| `tests/gui/controller/test_flatpak_admin_actions.py` | 0.004187 | 0.004127 | 0.004276 |
| `tests/cli/test_ancillary_logging.py` | 0.004067 | 0.003001 | 0.004404 |
| `tests/utils/test_validations.py` | 0.004050 | 0.004047 | 0.004096 |
| `tests/integration/test_pytrain_api_exit.py` | 0.003644 | 0.003608 | 0.003741 |
| `tests/gui/test_lcs_icons.py` | 0.003564 | 0.002939 | 0.005420 |
| `tests/db/test_client_state_listener.py` | 0.003529 | 0.003057 | 0.003747 |
| `tests/pdi/test_constants.py` | 0.003415 | 0.003356 | 0.003466 |
| `tests/gpio/utils/test_text_buffer.py` | 0.003412 | 0.003306 | 0.003521 |
| `tests/utils/test_unique_deque.py` | 0.003343 | 0.003189 | 0.003364 |
| `tests/pdi/test_base3_buffer.py` | 0.003273 | 0.003173 | 0.003909 |
| `tests/gui/test_catalog_panel.py` | 0.003160 | 0.003027 | 0.003343 |
| `tests/gui/test_accessory_cache_root.py` | 0.003140 | 0.003018 | 0.003160 |
| `tests/pdi/test_pdi_listener.py` | 0.003115 | 0.003011 | 0.003234 |
| `tests/protocol/test_constants.py` | 0.002986 | 0.002965 | 0.003496 |
| `tests/utils/test_singleton.py` | 0.002841 | 0.002828 | 0.002889 |
| `tests/pdi/test_pdi_req.py` | 0.002731 | 0.002701 | 0.002919 |
| `tests/gui/test_touch_list.py` | 0.002706 | 0.002530 | 0.002739 |
| `tests/gui/test_dummy_gui_components.py` | 0.002619 | 0.002579 | 0.002757 |
| `tests/utils/test_host_info.py` | 0.002563 | 0.002490 | 0.002682 |
| `tests/utils/test_argument_parser.py` | 0.002530 | 0.002441 | 0.002662 |
| `tests/pdi/test_lcs_req.py` | 0.002510 | 0.002344 | 0.002600 |
| `tests/utils/test_logging_manager.py` | 0.002387 | 0.002273 | 0.002464 |
| `tests/gui/test_wide_component_state_gui.py` | 0.002266 | 0.002106 | 0.002683 |
| `tests/gui/test_state_info_overlay.py` | 0.002120 | 0.002021 | 0.002278 |
| `tests/gpio/i2c/test_mcp23017.py` | 0.002117 | 0.002114 | 0.002293 |
| `tests/utils/test_flatpak_updates.py` | 0.002048 | 0.001983 | 0.002371 |
| `tests/utils/test_wifi_info.py` | 0.001956 | 0.001791 | 0.001980 |
| `tests/pdi/test_amc2_req.py` | 0.001806 | 0.001774 | 0.001872 |
| `tests/pdi/test_asc2_req.py` | 0.001803 | 0.001780 | 0.001842 |
| `tests/gui/controller/test_flatpak_update_indicator.py` | 0.001774 | 0.001688 | 0.001795 |
| `tests/atc/test_block.py` | 0.001773 | 0.001727 | 0.001777 |
| `tests/utils/test_cache_directory.py` | 0.001757 | 0.001740 | 0.001999 |
| `tests/gui/accessory/test_accessory_registry.py` | 0.001582 | 0.001573 | 0.001850 |
| `tests/db/test_state_watcher.py` | 0.001554 | 0.001501 | 0.001691 |
| `tests/utils/test_expiring_set.py` | 0.001548 | 0.001464 | 0.001565 |
| `tests/gui/controller/test_rr_speed_panel.py` | 0.001523 | 0.001492 | 0.001640 |
| `tests/pdi/test_d4_req.py` | 0.001459 | 0.001452 | 0.001472 |
| `tests/gui/controller/test_bell_horn_panel.py` | 0.001444 | 0.001440 | 0.001445 |
| `tests/pdi/test_pdi_state_store.py` | 0.001440 | 0.001401 | 0.001486 |
| `tests/gui/test_touch_scrollbar.py` | 0.001435 | 0.001350 | 0.001438 |
| `tests/test_version_tuple.py` | 0.001367 | 0.001211 | 0.001474 |
| `tests/pdi/test_bpc2_req.py` | 0.001344 | 0.001308 | 0.001359 |
| `tests/gui/controller/test_steam_deck_packaging.py` | 0.001285 | 0.001209 | 0.001414 |
| `tests/pdi/test_stm2_req.py` | 0.001179 | 0.001150 | 0.001202 |
| `tests/utils/test_pollable_queue.py` | 0.001147 | 0.001133 | 0.001357 |
| `tests/cli/test_cache.py` | 0.001145 | 0.001081 | 0.001350 |
| `tests/gui/test_scrolling_text.py` | 0.001136 | 0.001118 | 0.001287 |
| `tests/gpio/i2c/test_i2c.py` | 0.001112 | 0.001095 | 0.001134 |
| `tests/gui/accessory/test_accessories_gui_catalog.py` | 0.001106 | 0.001055 | 0.001161 |
| `tests/gpio/test_engine_status.py` | 0.001015 | 0.001003 | 0.001112 |
| `tests/gui/test_lcs_panel_wiring.py` | 0.001004 | 0.000984 | 0.001007 |
| `tests/utils/test_text_utils.py` | 0.001001 | 0.000947 | 0.001112 |
| `tests/protocol/test_validations.py` | 0.000450 | 0.000426 | 0.000470 |
| `tests/gpio/test_gpio_device.py` | 0.000254 | 0.000247 | 0.000273 |
| `tests/test_update_policy.py` | 0.000249 | 0.000237 | 0.000262 |
| `tests/protocol/test_command_base.py` | 0.000202 | 0.000188 | 0.000230 |
| `tests/gui/accessory/test_station_gui.py` | 0.000192 | 0.000186 | 0.000222 |

## Parameter families

| Item | Median | Min | Max |
|---|---:|---:|---:|
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log` | 1.472164 | 1.454899 | 1.508355 |
| `tests/cli/test_make_service.py::TestMakeService::test_parser` | 0.773499 | 0.763511 | 0.803714 |
| `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath` | 0.598745 | 0.596302 | 0.609071 |
| `tests/db/test_cache_sync.py::test_stop_without_listener_terminates_real_worker` | 0.504969 | 0.502568 | 0.506243 |
| `tests/cli/test_make_service.py::test_make_service_shell_script_includes_cache_sync_switch_only_when_disabled` | 0.418066 | 0.404278 | 0.449158 |
| `tests/cli/test_make_gui.py::test_make_gui_shell_script_includes_cache_sync_switch_only_when_disabled` | 0.399503 | 0.387613 | 0.410895 |
| `tests/cli/test_make_gui.py::test_shell_script_exports_the_platform_it_was_generated_for` | 0.395117 | 0.393550 | 0.397051 |
| `tests/cli/test_pytrain.py::test_parser_rejects_invalid_options` | 0.348369 | 0.339462 | 0.370096 |
| `tests/gui/controller/test_controls_panel.py::test_a_measured_ruler_reports_the_font_tk_will_draw_in` | 0.338461 | 0.329431 | 0.367955 |
| `tests/gui/test_route_builder_panel.py::test_successful_clear_hides_panel_through_popup_manager` | 0.216654 | 0.210299 | 0.217361 |
| `tests/gui/controller/test_engine_gui_compatibility.py::test_default_constructor_preserves_standalone_portrait_options` | 0.212749 | 0.210887 | 0.219286 |
| `tests/cli/test_lcs.py::test_host_defaults_to_the_portrait_overlay_geometry` | 0.210721 | 0.203553 | 0.305054 |
| `tests/protocol/sequence/test_speed_ramp.py::TestSpeedRamp::test_an_abort_waits_for_a_step_already_on_the_wire` | 0.201414 | 0.201408 | 0.202668 |
| `tests/gui/test_image_presenter.py::test_update_ignores_stale_engine_callback_for_other_scope` | 0.200611 | 0.200136 | 0.220878 |
| `tests/gui/test_route_builder_panel.py::test_desktop_wheel_browses_both_lists` | 0.177271 | 0.161877 | 0.178353 |
| `tests/utils/test_path_util.py::test_find_installation_dir` | 0.166351 | 0.165921 | 0.169882 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing` | 0.142179 | 0.141405 | 0.150865 |
| `tests/protocol/multibyte/test_ramp_command_req.py::test_variable_target_speed_roundtrip` | 0.130226 | 0.130066 | 0.132275 |
| `tests/test_pytest.py::TestPyTrain::test_get_version` | 0.119881 | 0.118568 | 0.123467 |
| `tests/cli/test_pytrain_pdi.py::test_pdi_requests` | 0.119874 | 0.115200 | 0.123492 |
| `tests/gui/test_route_builder_panel.py::test_pi_button_resize_ignores_unavailable_editor_geometry` | 0.113868 | 0.105844 | 0.117678 |
| `tests/gui/test_component_state_gui.py::test_cycle_gui_ignores_unknown_key` | 0.101518 | 0.101083 | 0.101645 |
| `tests/gui/test_touch_list_box.py::test_precise_horizontal_scroll_obeys_policy` | 0.094770 | 0.000908 | 0.112427 |
| `tests/protocol/sequence/test_speed_ramp_geometry.py::TestSpeedRampGeometry::test_bias_derived_from_the_base_table_and_clamped` | 0.094757 | 0.090568 | 0.099304 |
| `tests/gui/test_route_builder_panel.py::test_deck_picker_search_editing_blocks_selection_but_allows_cancel_and_halt` | 0.088762 | 0.006201 | 0.092108 |

## Setup phases

| Item | Median | Min | Max |
|---|---:|---:|---:|
| `tests/gui/test_route_builder_panel.py::test_desktop_wheel_browses_both_lists[win32--1-1-False]` | 0.096113 | 0.003041 | 0.104679 |
| `tests/gui/test_route_builder_panel.py::test_pi_button_resize_ignores_unavailable_editor_geometry[destroyed]` | 0.094879 | 0.003192 | 0.102020 |
| `tests/gui/test_touch_list_box.py::test_precise_horizontal_scroll_obeys_policy[True]` | 0.093929 | 0.000306 | 0.111666 |
| `tests/gui/test_route_builder_panel.py::test_deck_picker_search_editing_blocks_selection_but_allows_cancel_and_halt[dpad_left-None]` | 0.084379 | 0.001992 | 0.088076 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[True-0-0-True-darwin]` | 0.004887 | 0.002873 | 0.005194 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[True--30-2-False-darwin]` | 0.004695 | 0.002886 | 0.004773 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[True-0--40-True-darwin]` | 0.004679 | 0.002763 | 0.004942 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[False-0-1-False-darwin]` | 0.004642 | 0.002685 | 0.005240 |
| `tests/gui/test_route_builder_panel.py::test_desktop_picker_keys_use_current_filter_sort_and_scope[darwin-Switches-CommandScope.SWITCH]` | 0.004585 | 0.002831 | 0.004906 |
| `tests/gui/test_route_builder_panel.py::test_desktop_picker_double_click_adds_scrolled_component_and_returns_to_main[win32-Routes]` | 0.004544 | 0.002549 | 0.004930 |
| `tests/gui/test_route_builder_panel.py::test_desktop_wheel_browses_both_lists[win32-1--1-True]` | 0.004498 | 0.004154 | 0.109080 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[False-25-0-True-darwin]` | 0.004457 | 0.002827 | 0.004642 |
| `tests/gui/test_route_builder_panel.py::test_deck_analog_scrolls_picker_without_selecting_or_driving[context2-left]` | 0.004410 | 0.003986 | 0.005228 |
| `tests/gui/test_route_builder_panel.py::test_desktop_picker_double_click_outside_rows_does_not_add_selection[darwin-empty]` | 0.004390 | 0.002674 | 0.004449 |
| `tests/gui/test_route_builder_panel.py::test_route_metadata_editing_consumes_analog_input_without_scrolling[_number_field]` | 0.004317 | 0.001881 | 0.004716 |
| `tests/gui/test_route_builder_panel.py::test_pi_buttons_resize_stably_and_shrink_when_space_is_reduced` | 0.004307 | 0.003143 | 0.005033 |
| `tests/gui/test_route_builder_panel.py::test_pi_button_resize_ignores_unavailable_editor_geometry[hidden]` | 0.004258 | 0.004114 | 0.104935 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[False-0--40-True-darwin]` | 0.004256 | 0.002808 | 0.004298 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[True-0-1-False-darwin]` | 0.004250 | 0.003080 | 0.004382 |
| `tests/gui/test_route_builder_panel.py::test_desktop_wheel_browses_both_lists[win32--240-2-False]` | 0.004236 | 0.003155 | 0.004548 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[False--30-2-False-darwin]` | 0.004228 | 0.002908 | 0.005241 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[False--25-0-False-darwin]` | 0.004210 | 0.002941 | 0.004800 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[True--25-0-False-darwin]` | 0.004179 | 0.002990 | 0.004822 |
| `tests/gui/test_route_builder_panel.py::test_mac_touch_surface_scrolls_by_pixels_without_editing[False-0-0-True-darwin]` | 0.004164 | 0.003216 | 0.005062 |
| `tests/gui/test_route_builder_panel.py::test_desktop_picker_double_click_outside_rows_does_not_add_selection[win32-empty]` | 0.004147 | 0.002830 | 0.004488 |

## Call phases

| Item | Median | Min | Max |
|---|---:|---:|---:|
| `tests/cli/test_make_service.py::TestMakeService::test_parser` | 0.772910 | 0.763090 | 0.803333 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[spawn]` | 0.590079 | 0.581747 | 0.604475 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[forkserver]` | 0.568693 | 0.563936 | 0.587465 |
| `tests/db/test_cache_sync.py::test_stop_without_listener_terminates_real_worker` | 0.504494 | 0.502071 | 0.505771 |
| `tests/cli/test_make_service.py::test_make_service_shell_script_includes_cache_sync_switch_only_when_disabled` | 0.417321 | 0.403607 | 0.448490 |
| `tests/cli/test_make_gui.py::test_make_gui_shell_script_includes_cache_sync_switch_only_when_disabled` | 0.398750 | 0.386867 | 0.410166 |
| `tests/gui/controller/test_controls_panel.py::test_a_measured_ruler_reports_the_font_tk_will_draw_in` | 0.338288 | 0.329269 | 0.367792 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[fork]` | 0.312380 | 0.300541 | 0.313998 |
| `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath[False]` | 0.303646 | 0.300348 | 0.307578 |
| `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath[True]` | 0.296392 | 0.290709 | 0.299295 |
| `tests/gui/test_route_builder_panel.py::test_successful_clear_hides_panel_through_popup_manager` | 0.214796 | 0.208822 | 0.215660 |
| `tests/gui/controller/test_engine_gui_compatibility.py::test_default_constructor_preserves_standalone_portrait_options` | 0.212558 | 0.210674 | 0.219088 |
| `tests/cli/test_lcs.py::test_host_defaults_to_the_portrait_overlay_geometry` | 0.210226 | 0.203082 | 0.304830 |
| `tests/protocol/sequence/test_speed_ramp.py::TestSpeedRamp::test_an_abort_waits_for_a_step_already_on_the_wire` | 0.200595 | 0.200491 | 0.201449 |
| `tests/gui/test_image_presenter.py::test_update_ignores_stale_engine_callback_for_other_scope` | 0.200421 | 0.199913 | 0.220683 |
| `tests/cli/test_make_gui.py::test_shell_script_exports_the_platform_it_was_generated_for[SteamDeckGui-steamdeck]` | 0.198665 | 0.195780 | 0.198991 |
| `tests/cli/test_make_gui.py::test_shell_script_exports_the_platform_it_was_generated_for[EngineGui-]` | 0.196624 | 0.194713 | 0.197019 |
| `tests/utils/test_path_util.py::test_find_installation_dir` | 0.166095 | 0.165729 | 0.169686 |
| `tests/test_pytest.py::TestPyTrain::test_get_version` | 0.119413 | 0.118058 | 0.123008 |
| `tests/gui/test_component_state_gui.py::test_cycle_gui_ignores_unknown_key` | 0.101269 | 0.100833 | 0.101359 |
| `tests/cli/test_make_gui.py::test_make_gui_parser_accepts_no_cache_sync` | 0.072088 | 0.068216 | 0.078287 |
| `tests/gui/controller/test_engine_gui_conf_import.py::test_importing_engine_gui_conf_does_not_call_find_file` | 0.066833 | 0.001151 | 0.074625 |
| `tests/cli/test_make_gui.py::test_landscape_omits_desktop_autostart_by_default` | 0.054588 | 0.053080 | 0.054649 |
| `tests/cli/test_make_gui.py::test_make_gui_parser_constructs_landscape_controller` | 0.052424 | 0.051577 | 0.052473 |
| `tests/protocol/sequence/test_speed_ramp.py::TestSpeedRamp::test_an_abort_stalled_on_the_wire_still_completes` | 0.051812 | 0.051484 | 0.051870 |

## Teardown phases

| Item | Median | Min | Max |
|---|---:|---:|---:|
| `tests/db/test_cache_sync.py::test_stop_from_owned_thread_rejects_self_join_and_retains_manager[worker]` | 0.000940 | 0.000181 | 0.001411 |
| `tests/utils/test_wifi_info.py::test_macos_airport_output_is_parsed` | 0.000880 | 0.000797 | 0.000915 |
| `tests/cli/test_pytrain.py::test_parser_rejects_invalid_options[args3]` | 0.000636 | 0.000626 | 0.000696 |
| `tests/cli/test_pytrain.py::test_parser_rejects_invalid_options[args4]` | 0.000625 | 0.000565 | 0.000642 |
| `tests/db/test_cache_sync.py::test_join_timeout_retains_ownership_until_thread_terminates[worker]` | 0.000625 | 0.000217 | 0.000631 |
| `tests/cli/test_pytrain.py::test_parser_rejects_invalid_options[args2]` | 0.000624 | 0.000572 | 0.000627 |
| `tests/cli/test_pytrain.py::test_parser_rejects_invalid_options[args5]` | 0.000603 | 0.000558 | 0.000625 |
| `tests/cli/test_pytrain.py::test_parser_defaults` | 0.000599 | 0.000584 | 0.000645 |
| `tests/cli/test_pytrain.py::test_parser_rejects_invalid_options[args1]` | 0.000592 | 0.000532 | 0.000681 |
| `tests/cli/test_pytrain.py::test_parser_rejects_invalid_options[args0]` | 0.000588 | 0.000539 | 0.000593 |
| `tests/cli/test_pytrain.py::test_parser_rejects_invalid_options[args6]` | 0.000578 | 0.000564 | 0.000639 |
| `tests/cli/test_pytrain_update.py::test_update_subprocess_keyboard_interrupt_propagates_without_retry_or_relaunch[package-pip]` | 0.000513 | 0.000450 | 0.000520 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[spawn]` | 0.000416 | 0.000345 | 0.000458 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[fork]` | 0.000410 | 0.000373 | 0.000451 |
| `tests/protocol/sequence/test_speed_ramp.py::TestSpeedRamp::test_an_abort_stalled_on_the_wire_still_completes` | 0.000408 | 0.000178 | 0.000452 |
| `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log[forkserver]` | 0.000406 | 0.000373 | 0.000419 |
| `tests/db/test_cache_sync.py::test_build_serializes_with_stop_and_retains_failed_stop[False]` | 0.000378 | 0.000310 | 0.000404 |
| `tests/cli/test_pytrain.py::test_server_startup[args0-192.0.2.30-50001-False]` | 0.000378 | 0.000373 | 0.000431 |
| `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath[True]` | 0.000364 | 0.000345 | 0.000602 |
| `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath[False]` | 0.000356 | 0.000350 | 0.000360 |
| `tests/test_pytest.py::TestPyTrain::test_get_version` | 0.000355 | 0.000345 | 0.000391 |
| `tests/db/test_cache_sync.py::test_stop_without_listener_terminates_real_worker` | 0.000338 | 0.000330 | 0.000339 |
| `tests/pdi/test_base_req.py::test_incoming_speed_update_carries_target[stopped-2d-99-train]` | 0.000327 | 0.000074 | 0.000419 |
| `tests/utils/test_ip_tools.py::test_get_ip_address_non_linux_retries_until_success` | 0.000322 | 0.000314 | 0.000365 |
| `tests/cli/test_make_service.py::TestMakeService::test_parser` | 0.000311 | 0.000274 | 0.000483 |

## Fixture setup totals

Exclusive of dependency setup; includes fixture hook overhead. Finalizers are attributed only to case teardown, not individual fixtures.

| Fixture (source) | Invocations/run | Median total |
|---|---:|---:|
| `panel (tests/gui/test_route_builder_panel.py)` | 317 | 0.845854 |
| `pdi_send (tests/protocol/sequence/conftest.py)` | 859 | 0.278718 |
| `desktop_panel (tests/gui/test_route_builder_panel.py)` | 89 | 0.117338 |
| `tmp_path (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/tmpdir.py)` | 282 | 0.111452 |
| `runtime (tests/cli/test_pytrain_runtime.py)` | 144 | 0.100675 |
| `mod (tests/gui/test_touch_list_box.py)` | 19 | 0.096919 |
| `transport (tests/cli/test_pytrain_pdi.py)` | 140 | 0.055147 |
| `admin (tests/cli/test_pytrain_admin.py)` | 134 | 0.039819 |
| `ramp_target_update (tests/protocol/sequence/conftest.py)` | 131 | 0.036761 |
| `monkeypatch (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/monkeypatch.py)` | 3832 | 0.031485 |
| `pytrain_isolation (tests/cli/conftest.py)` | 667 | 0.028607 |
| `command_train (tests/cli/test_pytrain_commands.py)` | 55 | 0.027005 |
| `deck_picker (tests/gui/test_route_builder_panel.py)` | 53 | 0.024531 |
| `editable_text_module (tests/gui/test_editable_text.py)` | 75 | 0.023538 |
| `state_train (tests/cli/test_pytrain_state.py)` | 46 | 0.019619 |
| `pytrain_startup (tests/cli/conftest.py)` | 16 | 0.018558 |
| `host (tests/gui/test_routes_gui.py)` | 29 | 0.013934 |
| `pi_panel (tests/gui/test_route_builder_panel.py)` | 6 | 0.012480 |
| `cache_service (tests/cli/test_cache_sync_service.py)` | 25 | 0.011535 |
| `discovery (tests/cli/test_pytrain_service_discovery.py)` | 21 | 0.011027 |
| `command (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 953 | 0.010828 |
| `scope (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 976 | 0.010241 |
| `_xunit_setup_method_fixture_TestSpeedRampGeometry (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 523 | 0.009481 |
| `repo_root (tests/cli/test_pytrain_update.py)` | 40 | 0.008499 |
| `address (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 729 | 0.007447 |
| `bare_pytrain (tests/cli/conftest.py)` | 667 | 0.006114 |
| `speed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 538 | 0.005717 |
| `expected (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 481 | 0.005004 |
| `_patch_widgets (tests/gui/test_lcs_config_panel.py)` | 424 | 0.004586 |
| `outbound_speed_lookups (tests/pdi/test_base_req.py)` | 130 | 0.003649 |
| `isolated_state_store (tests/db/test_comp_data.py)` | 361 | 0.003586 |
| `caplog (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/logging.py)` | 273 | 0.003549 |
| `io (tests/db/test_irda_state.py)` | 55 | 0.003303 |
| `config (tests/test_deck_packaging.py)` | 7 | 0.002760 |
| `text (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 185 | 0.002744 |
| `state (tests/db/test_ramp_claim_state.py)` | 73 | 0.002744 |
| `field (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 197 | 0.002497 |
| `action (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 179 | 0.002377 |
| `native_speed_state (tests/pdi/test_base_req.py)` | 20 | 0.002270 |
| `capsys (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/capture.py)` | 73 | 0.002154 |
| `offset (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 223 | 0.002131 |
| `api_cache_shutdown (tests/cli/test_pytrain_admin.py)` | 8 | 0.002128 |
| `pin_process_globals (tests/db/test_engine_state_core.py)` | 229 | 0.002124 |
| `sync_dispatch (tests/pdi/test_base_req.py)` | 48 | 0.001923 |
| `lifecycle (tests/db/test_cache_sync.py)` | 14 | 0.001891 |
| `state_lookups (tests/pdi/test_irda_req.py)` | 68 | 0.001891 |
| `valid2 (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 175 | 0.001808 |
| `valid1 (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 181 | 0.001780 |
| `mode (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 141 | 0.001753 |
| `bias (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 181 | 0.001744 |
| `proxy (tests/comm/test_comm_buffer_proxy_disconnect.py)` | 7 | 0.001738 |
| `fake_socket (tests/comm/test_comm_buffer_proxy_disconnect.py)` | 7 | 0.001733 |
| `_xunit_setup_method_fixture_TestCommandReq (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 104 | 0.001690 |
| `name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 133 | 0.001664 |
| `_xunit_setup_method_fixture_TestSpeedRamp (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 84 | 0.001607 |
| `label (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 157 | 0.001595 |
| `is_ramping (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 144 | 0.001530 |
| `data (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 155 | 0.001519 |
| `_xunit_setup_method_fixture_TestSpeedToRpm (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 88 | 0.001516 |
| `compact (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 128 | 0.001505 |
| `_patch_runtime (tests/gui/test_guizero_base.py)` | 47 | 0.001430 |
| `build_deck (tests/test_deck_packaging.py)` | 8 | 0.001401 |
| `address_bytes (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 156 | 0.001380 |
| `speed_update_lookups (tests/pdi/test_base_req.py)` | 46 | 0.001376 |
| `claimed_update (tests/cli/test_pytrain_update.py)` | 35 | 0.001374 |
| `data_cls (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 117 | 0.001348 |
| `current (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 128 | 0.001293 |
| `target (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 119 | 0.001258 |
| `builder (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 102 | 0.001243 |
| `already_set (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 140 | 0.001221 |
| `error (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 96 | 0.001206 |
| `target_speed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 134 | 0.001170 |
| `api (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 90 | 0.001119 |
| `stage (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 61 | 0.001099 |
| `tmcc_id (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 86 | 0.001068 |
| `value (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 90 | 0.001065 |
| `_xunit_setup_method_fixture_TestRampSpeedReq (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 68 | 0.001061 |
| `_patch_widgets (tests/gui/test_keypad_view.py)` | 124 | 0.001052 |
| `operation (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 13 | 0.001046 |
| `max_speed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 91 | 0.001031 |
| `tmpdir (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/legacypath.py)` | 97 | 0.001015 |
| `kind (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 77 | 0.000999 |
| `size (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 80 | 0.000963 |
| `engine_type (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 88 | 0.000950 |
| `width (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 62 | 0.000940 |
| `previous_type (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 72 | 0.000933 |
| `pin_process_globals (tests/db/test_engine_state.py)` | 96 | 0.000918 |
| `reverse (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 94 | 0.000908 |
| `_xunit_setup_function_fixture_tests.db.test_prod_info (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000901 |
| `horizontal (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 58 | 0.000886 |
| `_xunit_setup_method_fixture_TestComponentState (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 64 | 0.000829 |
| `momentum (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 50 | 0.000818 |
| `prop (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 39 | 0.000811 |
| `enabled (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 68 | 0.000748 |
| `sensor (tests/db/test_irda_state.py)` | 53 | 0.000729 |
| `_no_display (tests/gui/test_checkbox_group.py)` | 113 | 0.000717 |
| `dx (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 62 | 0.000716 |
| `flags (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 47 | 0.000686 |
| `is_legacy (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 65 | 0.000679 |
| `mutation (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 52 | 0.000665 |
| `clean_logging (tests/utils/test_dual_logging.py)` | 10 | 0.000642 |
| `pytrain (tests/cli/test_routes.py)` | 24 | 0.000642 |
| `pending (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 54 | 0.000641 |
| `delta (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 57 | 0.000620 |
| `dy (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 62 | 0.000617 |
| `raw (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 52 | 0.000616 |
| `use_factory (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 72 | 0.000611 |
| `sandbox (tests/test_deck_packaging.py)` | 4 | 0.000593 |
| `args (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 46 | 0.000591 |
| `sequence (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 45 | 0.000588 |
| `timestamp_ms (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 60 | 0.000586 |
| `no_comm_buffer (tests/db/test_engine_state.py)` | 74 | 0.000582 |
| `from_tmcc_rx (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 32 | 0.000580 |
| `_patch_widgets (tests/gui/test_gui_checkpoint.py)` | 65 | 0.000572 |
| `real_exit_runtime (tests/cli/test_pytrain_runtime.py)` | 4 | 0.000571 |
| `cmd_line (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 42 | 0.000571 |
| `mock_comm_external_io (tests/comm/conftest.py)` | 1 | 0.000555 |
| `_xunit_setup_method_fixture_TestRampArbitration (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 36 | 0.000553 |
| `payload (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 29 | 0.000537 |
| `entry_point (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 52 | 0.000522 |
| `code (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 43 | 0.000508 |
| `filter_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 36 | 0.000498 |
| `reset_singletons (tests/db/test_component_state_store_ai.py)` | 44 | 0.000477 |
| `digit (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 33 | 0.000464 |
| `initialized_update_state (tests/pdi/test_base_req.py)` | 44 | 0.000450 |
| `is_package (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 39 | 0.000445 |
| `legacy (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 36 | 0.000445 |
| `_patch_widgets (tests/gui/test_gui_deck_parity.py)` | 52 | 0.000444 |
| `_no_display (tests/gui/test_scroll_box.py)` | 61 | 0.000443 |
| `run_before_and_after_tests (tests/db/test_component_state.py)` | 64 | 0.000440 |
| `length (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 38 | 0.000433 |
| `signed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 46 | 0.000420 |
| `_xunit_setup_method_fixture_TestCommandDispatcher (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 28 | 0.000412 |
| `context (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 31 | 0.000404 |
| `_xunit_setup_method_fixture_TestEchoLedger (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 27 | 0.000404 |
| `is_rx (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 32 | 0.000374 |
| `editor (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 30 | 0.000374 |
| `road_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000365 |
| `panel (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 27 | 0.000363 |
| `_xunit_setup_method_fixture_TestEchoFamily (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000360 |
| `expected_brake (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000359 |
| `bit (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 24 | 0.000357 |
| `height (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 31 | 0.000349 |
| `service (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000348 |
| `platform (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 24 | 0.000343 |
| `system (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 26 | 0.000343 |
| `wait_command (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 35 | 0.000343 |
| `gui_class (tests/cli/test_routes.py)` | 19 | 0.000342 |
| `smoke (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 33 | 0.000341 |
| `verb (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 36 | 0.000341 |
| `touch_list (tests/gui/test_touch_list.py)` | 9 | 0.000334 |
| `options (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000333 |
| `engine_id (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 27 | 0.000329 |
| `feature (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 28 | 0.000320 |
| `server (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 23 | 0.000320 |
| `linux (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 27 | 0.000312 |
| `bundled_font (tests/gui/test_bundled_fonts.py)` | 12 | 0.000307 |
| `port (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 29 | 0.000301 |
| `status (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 26 | 0.000301 |
| `failure (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 21 | 0.000298 |
| `_xunit_setup_method_fixture_TestTwoControllerRamp (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 19 | 0.000296 |
| `control_type (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 25 | 0.000296 |
| `direction (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 27 | 0.000296 |
| `host (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 23 | 0.000291 |
| `claimed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000289 |
| `button (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 27 | 0.000278 |
| `peers (tests/protocol/sequence/test_ramp_peer.py)` | 32 | 0.000268 |
| `engine_states (tests/protocol/sequence/test_ramp_peer.py)` | 23 | 0.000267 |
| `unavailable (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 17 | 0.000265 |
| `desktop (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 18 | 0.000264 |
| `initial (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 28 | 0.000263 |
| `late_action (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 30 | 0.000262 |
| `module (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 18 | 0.000258 |
| `attribute (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 25 | 0.000255 |
| `packet (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 26 | 0.000252 |
| `_xunit_setup_method_fixture_TestRampRegistry (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000252 |
| `patch_guizero_and_system (tests/gui/test_dummy_gui_components.py)` | 6 | 0.000252 |
| `mock_network_wait (tests/utils/test_ip_tools.py)` | 22 | 0.000252 |
| `send_request (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 28 | 0.000248 |
| `data_bytes (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000248 |
| `style (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 26 | 0.000248 |
| `inherited (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000230 |
| `module_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000229 |
| `stop (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 16 | 0.000225 |
| `button_size (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000223 |
| `position (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 24 | 0.000216 |
| `raw_target (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 24 | 0.000214 |
| `headless (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 21 | 0.000214 |
| `tmcc_target (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 24 | 0.000212 |
| `commands (tests/cli/test_pytrain_update.py)` | 25 | 0.000210 |
| `run_before_and_after_tests (tests/comm/test_dispatch_listener.py)` | 28 | 0.000208 |
| `one_process (tests/protocol/sequence/test_two_controller_ramp.py)` | 19 | 0.000208 |
| `encoded (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 22 | 0.000207 |
| `tmcc_speed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000205 |
| `chain (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 16 | 0.000205 |
| `properties (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 17 | 0.000203 |
| `state_cls (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 19 | 0.000202 |
| `no_wait (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 21 | 0.000200 |
| `tag (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 15 | 0.000197 |
| `level (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000195 |
| `needs (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000194 |
| `key (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 17 | 0.000190 |
| `instance (tests/gui/test_dummy_gui_components.py)` | 1 | 0.000189 |
| `as_action (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000188 |
| `sync (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 21 | 0.000188 |
| `method (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 16 | 0.000188 |
| `road_number (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 18 | 0.000187 |
| `units (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000187 |
| `tmcc_packets (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000184 |
| `index (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000183 |
| `parts (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000180 |
| `device (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000179 |
| `mac_platform (tests/gui/test_swipe_detector.py)` | 25 | 0.000179 |
| `rpm (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 16 | 0.000177 |
| `unmeasured (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000177 |
| `legacy_speed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000177 |
| `legacy_packets (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 20 | 0.000175 |
| `train_id (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 18 | 0.000175 |
| `on (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 18 | 0.000171 |
| `ramp_status (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000170 |
| `cache_failure (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 17 | 0.000167 |
| `_xunit_setup_method_fixture_TestConstants (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000167 |
| `owned_thread (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000167 |
| `state (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000164 |
| `expected_height (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000159 |
| `policy (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000157 |
| `show_unlabeled (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000157 |
| `_patch_runtime (tests/cli/test_lcs.py)` | 13 | 0.000156 |
| `build_component_store (tests/db/test_startup_state.py)` | 9 | 0.000156 |
| `error_type (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000155 |
| `_patch_widgets (tests/gui/test_motors_gui.py)` | 17 | 0.000152 |
| `action_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000152 |
| `reg (tests/gui/accessory/test_accessory_registry.py)` | 7 | 0.000151 |
| `scrolls (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 16 | 0.000150 |
| `no_thread_start (tests/db/test_startup_state.py)` | 9 | 0.000149 |
| `destination (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 16 | 0.000145 |
| `catalog (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 16 | 0.000143 |
| `source (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 11 | 0.000141 |
| `reset_singleton (tests/comm/test_enqueue_proxy_requests.py)` | 16 | 0.000141 |
| `budget (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000140 |
| `available (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 15 | 0.000139 |
| `parsed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 16 | 0.000139 |
| `brake (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000138 |
| `same_millisecond (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 16 | 0.000135 |
| `leading_rx (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000135 |
| `invalid (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000134 |
| `_patch_widgets (tests/gui/test_amc2_ops_panel.py)` | 14 | 0.000130 |
| `title_overhead (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000130 |
| `returncode (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000129 |
| `reading (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000129 |
| `is_cab1 (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 13 | 0.000128 |
| `sort (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000126 |
| `refresh (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000126 |
| `startup (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000126 |
| `failure_point (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000125 |
| `device_key (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000125 |
| `number (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 11 | 0.000124 |
| `family (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000124 |
| `include_state (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000122 |
| `suffix (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000122 |
| `platform_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000121 |
| `expected_momentum (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 14 | 0.000120 |
| `location (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000115 |
| `requested_speed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000115 |
| `deck (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000114 |
| `start (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 11 | 0.000114 |
| `rate (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000114 |
| `search (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000114 |
| `result (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 11 | 0.000112 |
| `engine_packet (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000111 |
| `expected_scope (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 11 | 0.000111 |
| `request_type (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000111 |
| `flag (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000111 |
| `values (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000110 |
| `use_subclass (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000109 |
| `patch_gui_classes (tests/gui/test_component_state_gui.py)` | 7 | 0.000109 |
| `cls (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000107 |
| `train_packet (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 12 | 0.000105 |
| `enum_cls (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000105 |
| `alias (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000104 |
| `patched_engine_status (tests/gpio/test_engine_status.py)` | 4 | 0.000104 |
| `protocol (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000103 |
| `event (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000101 |
| `_patch_registry_and_catalog (tests/gui/accessory/test_accessory_gui.py)` | 10 | 0.000100 |
| `side (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000100 |
| `service_failure (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000100 |
| `unsafe_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000099 |
| `expected_start (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000099 |
| `class_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000098 |
| `rows (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000098 |
| `cmd_enum (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000097 |
| `is_reverse (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000097 |
| `reset_singleton_state (tests/db/test_client_state_listener.py)` | 9 | 0.000096 |
| `_xunit_setup_method_fixture_TestBlock (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000094 |
| `title (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000094 |
| `pane (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000094 |
| `claim_id (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000093 |
| `asked (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000093 |
| `refresh_before_release (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000092 |
| `is_forward (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000092 |
| `descending (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000091 |
| `is_server (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000091 |
| `_isolate (tests/gui/accessory/test_accessory_gui.py)` | 10 | 0.000089 |
| `query (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000088 |
| `user_defined (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000088 |
| `_xunit_setup_method_fixture_TestPyTrain (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000086 |
| `req_cls (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000086 |
| `engine_target (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 10 | 0.000086 |
| `discovers (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000086 |
| `debug (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000084 |
| `thru (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000083 |
| `release (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000083 |
| `present (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000082 |
| `expected_base (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000080 |
| `event_type (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000080 |
| `initialized (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000079 |
| `is_d4 (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000078 |
| `comp_data (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000078 |
| `addresses (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000078 |
| `dispatcher (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000078 |
| `bluetooth_id (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000077 |
| `found (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000077 |
| `known_server (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 9 | 0.000075 |
| `ident (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000075 |
| `include_lcs (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000075 |
| `mode_key (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000074 |
| `_patch_classes (tests/gui/test_wide_component_state_gui.py)` | 6 | 0.000074 |
| `expected_id (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000073 |
| `popup_visible (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000073 |
| `clear_info (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000072 |
| `root_at_info (tests/cli/test_pytrain_service_discovery.py)` | 4 | 0.000072 |
| `gui_class (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000072 |
| `enter_key (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000071 |
| `percentage (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000071 |
| `replacement (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000071 |
| `original (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000071 |
| `base (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000070 |
| `clean_singletons (tests/pdi/test_pdi_listener.py)` | 6 | 0.000070 |
| `route (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000068 |
| `labeled (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000068 |
| `resolved_id (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 8 | 0.000067 |
| `params (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000067 |
| `header_height (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000066 |
| `capable (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000066 |
| `remainder (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000065 |
| `is_api (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000065 |
| `refusal (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000064 |
| `state_type (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000064 |
| `details (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000063 |
| `_xunit_setup_method_fixture_TestI2c (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000063 |
| `sort_order (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000063 |
| `bar_width (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000061 |
| `has_address (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 7 | 0.000061 |
| `version (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000060 |
| `count (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000060 |
| `kwargs (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000060 |
| `styled (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000060 |
| `cramped (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000059 |
| `_xunit_setup_method_fixture_TestCommandListener (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000059 |
| `unsafe_path (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000059 |
| `buttons (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000059 |
| `missing (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000059 |
| `clean_singletons (tests/pdi/test_base3_buffer.py)` | 6 | 0.000059 |
| `packaged (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000058 |
| `show_keyboard (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000058 |
| `speed_limit (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000058 |
| `notches (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000057 |
| `tmcc (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000057 |
| `moved (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000057 |
| `reset_listener_singleton (tests/comm/test_command_listener_ai.py)` | 5 | 0.000056 |
| `diagnostic (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000056 |
| `exception (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000056 |
| `existing (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000055 |
| `scale_by (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000055 |
| `foreign (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000053 |
| `spare (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000053 |
| `hat (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000053 |
| `real (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000052 |
| `success (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000052 |
| `fake_time (tests/utils/test_expiring_set.py)` | 7 | 0.000052 |
| `first_command (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000052 |
| `same_host (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000052 |
| `second_button (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000051 |
| `help_text (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000051 |
| `hostname (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000051 |
| `extra (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000051 |
| `wide (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000051 |
| `pad_x (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000051 |
| `queue_present (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000051 |
| `widget_factory (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000051 |
| `motor1_restore (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000051 |
| `info (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000051 |
| `do_async (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000050 |
| `interrupt (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000050 |
| `from_root (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000049 |
| `pad_y (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 6 | 0.000049 |
| `launcher_factory (tests/cli/test_make_gui.py)` | 4 | 0.000049 |
| `gap (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000049 |
| `is_base (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000048 |
| `px_per_char (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000048 |
| `y (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000048 |
| `digit_count (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000047 |
| `reset_singletons (tests/pdi/test_base3_buffer.py)` | 3 | 0.000047 |
| `package (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000046 |
| `expected_defaults (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 5 | 0.000046 |
| `manager (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000046 |
| `reboot (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000045 |
| `soft_status (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000045 |
| `lcs_req (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000045 |
| `echo_error (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000044 |
| `motor2_restore (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000044 |
| `selected (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000043 |
| `pdi (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000043 |
| `cleared (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000042 |
| `is_ser2 (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000042 |
| `speeds (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000041 |
| `held_before_claim (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000041 |
| `state_kind (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000041 |
| `stand_alone (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000041 |
| `connection (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000040 |
| `script (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000040 |
| `sort_key (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000040 |
| `font_size (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000040 |
| `base_id (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000040 |
| `as_request (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000039 |
| `loco_rl (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000039 |
| `callback_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000039 |
| `missing_native (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000039 |
| `age (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000039 |
| `skipped (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000038 |
| `output_type (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000038 |
| `queue (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000038 |
| `pending_step (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000037 |
| `from_ops (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000037 |
| `ser2 (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000037 |
| `_patch_panel (tests/gui/test_lcs_panel_wiring.py)` | 4 | 0.000037 |
| `expected_pdi_command (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000037 |
| `root_at_info (tests/cli/test_pytrain_debug_toggle.py)` | 2 | 0.000037 |
| `extended (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000036 |
| `controller_view (tests/gui/test_controller_view.py)` | 1 | 0.000036 |
| `failures (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000036 |
| `owns_window (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000035 |
| `remote (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000035 |
| `components (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000035 |
| `thread (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000035 |
| `below (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000035 |
| `report (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000035 |
| `num_ids (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000034 |
| `view (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000034 |
| `reset_singleton (tests/pdi/test_pdi_state_store.py)` | 4 | 0.000034 |
| `required_height (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 4 | 0.000034 |
| `loco_id (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000034 |
| `role (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000033 |
| `config (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000033 |
| `zeroconf (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000032 |
| `run_before_and_after_tests (tests/comm/test_command_listener.py)` | 4 | 0.000031 |
| `cancel_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000031 |
| `allow (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000031 |
| `scale (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000031 |
| `is_tmcc (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000030 |
| `settling (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000030 |
| `field_name (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000030 |
| `parent (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000030 |
| `touch (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000030 |
| `loco_lr (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000029 |
| `back_reference (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000029 |
| `retry_interrupted (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000029 |
| `guid (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000029 |
| `row (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000028 |
| `parent_gui (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000028 |
| `indirect (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000028 |
| `prefix (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000028 |
| `mock_pdi_dispatcher_ip (tests/pdi/conftest.py)` | 1 | 0.000028 |
| `synchronized (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000028 |
| `yes_focused (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000028 |
| `controller (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000028 |
| `explicit (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000027 |
| `exists (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000027 |
| `row_height (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000027 |
| `right_to_left (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000027 |
| `discard_focused (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000027 |
| `server_version (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000027 |
| `windowing_system (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000027 |
| `_unittest_setUpClass_fixture_TestMCP23017 (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/unittest.py)` | 1 | 0.000026 |
| `payload_type (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000026 |
| `left_to_right (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000026 |
| `expected_rl (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000026 |
| `expected_lr (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000026 |
| `echo (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 3 | 0.000026 |
| `canceled (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000026 |
| `restore (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000025 |
| `state_change (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000025 |
| `header_available (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000025 |
| `cancel_button (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000025 |
| `native (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000025 |
| `tick_before_claim (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000025 |
| `state_class (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000024 |
| `panel_kind (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000024 |
| `mock_command_dispatcher_ip (tests/db/conftest.py)` | 1 | 0.000024 |
| `acquired (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000024 |
| `pressed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000024 |
| `released (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000024 |
| `supported (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000024 |
| `do_fire (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000024 |
| `large (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000024 |
| `updates (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000024 |
| `stretch (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000023 |
| `managed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000023 |
| `pdi_command (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000023 |
| `parent_width (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000023 |
| `border_thickness (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000023 |
| `held (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000023 |
| `relaunch (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000022 |
| `preferred (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000022 |
| `controlled_keepalive (tests/pdi/test_base3_buffer.py)` | 2 | 0.000022 |
| `takeover_speed (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000022 |
| `_xunit_setup_method_fixture_TestMakeService (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 1 | 0.000021 |
| `exit_code (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000021 |
| `has_manager (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000021 |
| `dependency (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000021 |
| `parse_only (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000021 |
| `owns_ramp (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000021 |
| `expected_payload (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000020 |
| `registered (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000020 |
| `_xunit_setup_method_fixture_TestEngineStateRoutesThroughTheRegistry (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 1 | 0.000020 |
| `option_pad (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000019 |
| `ceiling (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000019 |
| `section (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000018 |
| `stdout (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000018 |
| `load_bundled (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000018 |
| `page (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000018 |
| `backend (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000018 |
| `note_pad (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000018 |
| `on_screen (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000018 |
| `_unittest_setUpClass_fixture_TestGPIODevice (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/unittest.py)` | 1 | 0.000017 |
| `_xunit_setup_method_fixture_TestValidations (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 1 | 0.000017 |
| `tmp_path_factory (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/tmpdir.py)` | 1 | 0.000017 |
| `id_page (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000017 |
| `echo_packet (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000017 |
| `sent_packet (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000017 |
| `prose (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000017 |
| `heading (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 2 | 0.000016 |
| `_xunit_setup_method_fixture_TestComponentStateStore (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/python.py)` | 1 | 0.000014 |
| `_unittest_setup_method_fixture_TestGPIODevice (/Users/davids/Documents/dev/PyLegacyEnv/lib/python3.13/site-packages/_pytest/unittest.py)` | 1 | 0.000013 |
| `run_before_and_after_tests (tests/db/test_component_state_store.py)` | 1 | 0.000007 |
