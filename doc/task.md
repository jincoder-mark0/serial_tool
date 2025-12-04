# Task List

## Phase 1: Project Setup (Completed)
- [x] Create project directory structure
- [x] Initialize git repository
- [x] Create virtual environment
- [x] Install dependencies (PyQt5)
- [x] Create README.md
- [x] Create .gitignore

## Phase 2: UI Implementation & Theme System (Completed)
- [x] Implement Main Window Layout
    - [x] Create `MainWindow` class
    - [x] Implement `LeftSection` (Port/Control)
    - [x] Implement `RightSection` (Command/Inspector)
- [x] Implement Widgets
    - [x] `PortSettingsWidget`
    - [x] `ReceivedArea` (Log View)
    - [x] `ManualControlWidget`
    - [x] `CommandListWidget`
    - [x] `CommandControlWidget`
    - [x] `PacketInspectorWidget`
    - [x] `FileProgressWidget`
- [x] Implement Theme System
    - [x] Create `ThemeManager`
    - [x] Create `common.qss`
    - [x] Create `dark_theme.qss`
    - [x] Create `light_theme.qss`
    - [x] Implement SVG Icon System
- [x] Implement Dual Font System
    - [x] Update `ThemeManager` for font handling
    - [x] Create `FontSettingsDialog`
    - [x] Apply fonts to widgets
- [x] Refactor Directory Structure
    - [x] Move widgets to `view/widgets`
    - [x] Move panels to `view/panels`
    - [x] Move dialogs to `view/dialogs`
    - [x] Create `view/sections` for Left/Right sections
- [x] Multi-language Support (Localization)
    - [x] Create `LanguageManager`
    - [x] Create `en.json` and `ko.json`
    - [x] Apply to `ManualControlWidget`
    - [x] Apply to `ReceivedArea`
    - [x] Apply to `CommandListWidget`
    - [x] Apply to `CommandControlWidget`
    - [x] Apply to `FileProgressWidget`
    - [x] Apply to `PacketInspectorWidget`
    - [x] Apply to `MainWindow` (Menus, Dock Titles)
    - [x] Apply to `LeftSection` & `RightSection` (Tabs)
    - [x] Apply to `PortSettingsWidget`
    - [x] Apply to `StatusArea`
    - [x] Apply to `FontSettingsDialog`
    - [x] Apply to `PreferencesDialog`

- [x] Refactoring & Stabilization
    - [x] Language Key Standardization (`[context]_[type]_[name]`)
    - [x] Update Code Style Guide (Naming Conventions)
    - [x] Fix Preferences Dialog Accessibility
    - [x] Implement Preferences Dialog Logic

## Phase 3: Core Utilities (In Progress)
- [ ] Implement `RingBuffer`
# Task List

## Phase 1: Project Setup (Completed)
- [x] Create project directory structure
- [x] Initialize git repository
- [x] Create virtual environment
- [x] Install dependencies (PyQt5)
- [x] Create README.md
- [x] Create .gitignore

## Phase 2: UI Implementation & Theme System (Completed)
- [x] Implement Main Window Layout
    - [x] Create `MainWindow` class
    - [x] Implement `LeftSection` (Port/Control)
    - [x] Implement `RightSection` (Command/Inspector)
- [x] Implement Widgets
    - [x] `PortSettingsWidget`
    - [x] `ReceivedArea` (Log View)
    - [x] `ManualControlWidget`
    - [x] `CommandListWidget`
    - [x] `CommandControlWidget`
    - [x] `PacketInspectorWidget`
    - [x] `FileProgressWidget`
- [x] Implement Theme System
    - [x] Create `ThemeManager`
    - [x] Create `common.qss`
    - [x] Create `dark_theme.qss`
    - [x] Create `light_theme.qss`
    - [x] Implement SVG Icon System
- [x] Implement Dual Font System
    - [x] Update `ThemeManager` for font handling
    - [x] Create `FontSettingsDialog`
    - [x] Apply fonts to widgets
- [x] Refactor Directory Structure
    - [x] Move widgets to `view/widgets`
    - [x] Move panels to `view/panels`
    - [x] Move dialogs to `view/dialogs`
    - [x] Create `view/sections` for Left/Right sections
- [x] Multi-language Support (Localization)
    - [x] Create `LanguageManager`
    - [x] Create `en.json` and `ko.json`
    - [x] Apply to `ManualControlWidget`
    - [x] Apply to `ReceivedArea`
    - [x] Apply to `CommandListWidget`
    - [x] Apply to `CommandControlWidget`
    - [x] Apply to `FileProgressWidget`
    - [x] Apply to `PacketInspectorWidget`
    - [x] Apply to `MainWindow` (Menus, Dock Titles)
    - [x] Apply to `LeftSection` & `RightSection` (Tabs)
    - [x] Apply to `PortSettingsWidget`
    - [x] Apply to `StatusArea`
    - [x] Apply to `FontSettingsDialog`
    - [x] Apply to `PreferencesDialog`

- [x] Refactoring & Stabilization
    - [x] Language Key Standardization (`[context]_[type]_[name]`)
    - [x] Update Code Style Guide (Naming Conventions)
    - [x] Fix Preferences Dialog Accessibility
    - [x] Implement Preferences Dialog Logic

## Phase 3: Core Utilities (In Progress)
- [ ] Implement `RingBuffer`
    - [ ] Create `core/utils.py`
    - [ ] Implement circular buffer logic
    - [ ] Thread-safety implementation
- [ ] Implement `ThreadSafeQueue`
    - [ ] Add to `core/utils.py`
    - [ ] Implement blocking/non-blocking queue
- [ ] Implement `EventBus`
    - [ ] Create `core/event_bus.py`
    - [ ] Implement Pub/Sub pattern
    - [ ] Define Standard Event Types (`core/event_types.py`)
- [ ] Implement `LogManager`
    - [ ] Create `core/logger.py`
    - [ ] Implement `RotatingFileHandler` (10MB limit)
    - [ ] Implement Performance Logger (CSV export)

## Phase 4: Model Layer (Planned)
- [ ] Implement `SerialWorker`
    - [ ] Create `model/serial_worker.py`
    - [ ] QThread implementation
- [ ] Implement `PortController`
    - [ ] Create `model/port_controller.py`
    - [ ] State machine implementation
- [ ] Implement `SerialManager` (PortRegistry)
    - [ ] Create `model/serial_manager.py`
    - [ ] Implement Port Registry & Lifecycle management
- [ ] Implement `PacketParser` System
    - [ ] Create `model/packet_parser.py`
    - [ ] Implement `ParserFactory` (AT, Delimiter, Fixed, Hex)
    - [ ] Implement `ExpectMatcher` (Regex based)
- [ ] Implement `EventRouter` (View-Model decoupling)
- [ ] Implement `PortPresenter` (Open/Close/Config)
- [ ] Implement `MainPresenter` (App Lifecycle)
- [ ] Implement `CommandPresenter` (CL Logic)
- [ ] Implement `FilePresenter` (Transfer Logic)
- [ ] CI/CD Setup

## Phase 6: Automation & Advanced Features (Planned)
- [ ] Implement `CLRunner` (Command List Engine)
    - [ ] State Machine (Idle/Running/Paused)
    - [ ] Step Execution (Send -> Expect -> Delay)
    - [ ] Auto Run Scheduler (Interval/Loops)
- [ ] Implement `FileTransferEngine`
    - [ ] Chunk-based Transfer (Adaptive Size)
    - [ ] Progress Calculation & Cancel Support
    - [ ] Rx Capture to File (`RxCaptureWriter`)
- [ ] Implement `AutoTxScheduler` (Periodic Send)
- [ ] Performance Optimization
    - [ ] Implement `BatchRenderer` for RxLogView
    - [ ] Optimize `RingBuffer` (bytearray)
    - [ ] Optimize Non-blocking I/O Loop

## Phase 7: Plugin System (Planned)
- [ ] Implement Plugin Infrastructure
    - [ ] Create `core/plugin_base.py` (Interface)
    - [ ] Create `core/plugin_loader.py` (Dynamic Import)
    - [ ] Implement `ExamplePlugin`

## Phase 8: Verification & Deployment (Planned)
- [ ] Test Environment Setup
    - [ ] Setup Virtual Serial Ports (com0com/socat)
    - [ ] Create Mock Serial Classes
- [ ] Automated Tests
    - [ ] Unit Tests (Core/Model)
    - [ ] Integration Tests (Serial I/O)
    - [ ] Performance Benchmarks (Rx Throughput, UI Render)
- [ ] Packaging & Deployment
    - [ ] Create `pyinstaller.spec`
    - [ ] Build Standalone EXE/AppImage
    - [ ] Setup GitHub Actions CI/CD
