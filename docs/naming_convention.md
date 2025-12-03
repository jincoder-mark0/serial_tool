# Language Key Naming Convention

To maintain consistency and readability in the localization files (`en.json`, `ko.json`) and the code, we will use the following naming convention for language keys.

## Format
`[context]_[type]_[name]_[suffix]`

*   **Case**: snake_case (lowercase with underscores)
*   **Context**: **Mandatory**. The widget or logical section the key belongs to.
*   **Type**: The UI element type (btn, lbl, etc.).

## Contexts (Widgets/Sections)

| Context | Description | Example |
| :--- | :--- | :--- |
| `global` | Shared across app | `global_btn_ok`, `global_msg_error` |
| `main` | Main Window | `main_menu_file`, `main_title` |
| `port` | Port Settings Widget | `port_lbl_baudrate`, `port_btn_connect` |
| `manual` | Manual Control Widget | `manual_btn_send`, `manual_chk_hex` |
| `cmd` | Command List/Control | `cmd_btn_add`, `cmd_col_command` |
| `recv` | Received Area Widget | `recv_btn_clear`, `recv_chk_timestamp` |
| `pref` | Preferences Dialog | `pref_lbl_font_size` |
| `about` | About Dialog | `about_title`, `about_lbl_version` |

## Types (UI Elements)

| Type | Description | Example |
| :--- | :--- | :--- |
| `title` | Window/Dialog titles | `main_title`, `about_title` |
| `menu` | Menu items | `main_menu_file` |
| `btn` | Buttons | `port_btn_connect` |
| `lbl` | Labels | `port_lbl_port` |
| `chk` | Checkboxes | `manual_chk_rts` |
| `grp` | GroupBoxes | `cmd_grp_auto` |
| `tab` | Tabs | `main_tab_port` |
| `col` | Table columns | `cmd_col_hex` |
| `msg` | Messages/Logs | `global_msg_saved` |
| `input` | Input placeholders | `manual_input_cmd` |

## Suffixes (Attribute)

| Suffix | Description | Example |
| :--- | :--- | :--- |
| `_tooltip` | Tooltip text | `port_btn_connect_tooltip` |
| `_placeholder` | Placeholder text | `manual_input_cmd_placeholder` |

## Examples

*   **Bad**: `save`, `btn_save` (ambiguous context), `port_baudrate` (missing type)
*   **Good**: `global_btn_save`, `port_lbl_baudrate`, `manual_chk_hex`
