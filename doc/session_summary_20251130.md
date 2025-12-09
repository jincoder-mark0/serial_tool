# 2025-11-30 개발 세션 요약

## 1. 세션 목표

- 프로젝트 명칭 변경(`SerialManager` -> `SerialTool`) 및 디렉토리 구조 재정리.
- Layered MVP 아키텍처 기반의 UI 골격(Skeleton) 완성.
- 주요 위젯(`CommandList`, `ManualControl`)의 기본 기능 구현 및 리팩토링.

## 2. 주요 변경 사항

### A. 프로젝트 구조 및 명칭 (Structure & Naming)

- **명칭 변경**: 프로젝트 이름을 `SerialManager`에서 **`SerialTool`**로 변경하고 관련 코드/문서 업데이트.
- **디렉토리 이동**: 소스 코드를 `serial_manager/` 하위로 이동하고, 가상 환경(`.venv`) 위치 조정.
- **모듈화**: `core`, `model`, `view`, `presenter` 패키지 구조 확립.

### B. UI 아키텍처 (UI Architecture)

- **패널 분리**: `MainWindow`를 **`LeftPanel`**(포트/수동제어)과 **`RightPanel`**(커맨드/인스펙터)로 분리하여 구조 단순화.
- **위젯 리팩토링**:
  - `view/widgets/` 패키지 생성 및 하위 위젯 분리.
  - `MacroListWidget`: 행 추가/삭제/이동 기능 및 체크박스 로직 구현.
  - `MacroCtrlWidget`: 스크립트 저장/로드 및 자동 실행 UI 추가.
  - `ManualControlWidget`: `OperationArea`를 재작성하여 수동 제어 기능 통합.

### C. 문서화 (Documentation)

- **README.md**: 프로젝트 개요, 설치 방법, 구조 설명 추가.
- **CHANGELOG.md**: 초기 버전(`v0.1.0`) 릴리스 노트 작성.
- **task.md**: 전체 작업 목록 및 진행 상황 추적 시작.

## 3. 비고

- 초기 개발 단계로서 UI의 기능적 기반을 마련하는 데 집중함.
- 이후 UI 디자인 개선(12/01) 및 Core 로직 구현으로 이어짐.
