"""
언어 키 관리 도구

    
    Returns:
        Dict[str, Set[str]]: 모듈명을 키로, 사용되는 키 집합을 값으로 하는 딕셔너리
    """
    view_dir = Path(__file__).parent.parent / "view"
    keys_by_module = defaultdict(set)
    
    for py_file in view_dir.rglob("*.py"):
        # 모듈 경로 생성 (예: widgets/manual_control, dialogs/font_settings)
        try:
            relative_path = py_file.relative_to(view_dir)
            module_path = str(relative_path.with_suffix('')).replace('\\', '/')
        except ValueError:
            continue
        
        content = py_file.read_text(encoding='utf-8')
        # get_text("key") 또는 get_text('key') 패턴 찾기
        matches = re.findall(r'get_text\(["\']([^"\']+)["\']\)', content)
        
        if matches:
            keys_by_module[module_path].update(matches)
    
    return keys_by_module

def get_module_display_name(module_path: str) -> str:
    """모듈 경로를 사람이 읽기 쉬운 이름으로 변환"""
    name_map = {
        'main_window': 'Main Window',
        'language_manager': 'Language Manager',
        'theme_manager': 'Theme Manager',
        'panels/left_panel': 'Left Panel',
        'panels/right_panel': 'Right Panel',
        'panels/port_panel': 'Port Panel',
        'panels/command_list_panel': 'Command List Panel',
        'widgets/port_settings': 'Port Settings Widget',
        'widgets/manual_control': 'Manual Control Widget',
        'widgets/received_area': 'Received Area Widget',
        'widgets/command_list': 'Command List Widget',
        'widgets/command_control': 'Command Control Widget',
        'widgets/packet_inspector': 'Packet Inspector Widget',
        'widgets/file_progress_widget': 'File Progress Widget',
        'widgets/status_area': 'Status Area Widget',
        'dialogs/font_settings_dialog': 'Font Settings Dialog',
        'dialogs/preferences_dialog': 'Preferences Dialog',
        'dialogs/about_dialog': 'About Dialog',
    }
    return name_map.get(module_path, module_path)

def generate_template(keys_by_module: Dict[str, Set[str]], output_file: str, language: str = "en"):
    """
    모듈별로 그룹화되고 주석이 추가된 언어 템플릿 파일을 생성합니다.
    
    Args:
        keys_by_module: 모듈별 키 딕셔너리
        output_file: 출력 파일 경로
        language: 언어 코드 ("en" 또는 "ko")
    """
    # 기존 JSON 파일이 있으면 값을 가져옴
    existing_values = {}
    if Path(output_file).exists():
        try:
            existing_values = json.loads(Path(output_file).read_text(encoding='utf-8'))
            # 주석 키 제거 (이전 버전에서 생성된 경우)
            existing_values = {k: v for k, v in existing_values.items() if not k.startswith("//")}
        except json.JSONDecodeError:
            print(f"⚠ 기존 템플릿 파일이 손상되어 새로 생성합니다: {output_file}")
            existing_values = {}
    
    # 모듈을 논리적 순서로 정렬
    module_order = [
        'main_window',
        'panels/left_panel',
        'panels/right_panel',
        'panels/port_panel',
        'panels/command_list_panel',
        'widgets/port_settings',
        'widgets/manual_control',
        'widgets/received_area',
        'widgets/command_list',
        'widgets/command_control',
        'widgets/packet_inspector',
        'widgets/file_progress_widget',
        'widgets/status_area',
        'dialogs/font_settings_dialog',
        'dialogs/preferences_dialog',
        'dialogs/about_dialog',
    ]
    
    # 정렬된 모듈 리스트 생성 (정의된 순서 + 나머지)
    sorted_modules = []
    for mod in module_order:
        if mod in keys_by_module:
            sorted_modules.append(mod)
    
    # 나머지 모듈 추가
    for mod in sorted(keys_by_module.keys()):
        if mod not in sorted_modules:
            sorted_modules.append(mod)
    
    # JSON 파일 생성 (주석은 별도 처리)
    lines = ["{\n"]
    
    # 공통 키들 (여러 모듈에서 사용)
    common_keys = set()
    key_count = defaultdict(int)
    for keys in keys_by_module.values():
        for key in keys:
            key_count[key] += 1
    
    # 3개 이상의 모듈에서 사용되는 키를 공통 키로 분류
    common_keys = {key for key, count in key_count.items() if count >= 3}
    
    # 공통 키 먼저 출력
    if common_keys:
        lines.append('  // ============================================\n')
        lines.append('  // Common Keys (Used in multiple modules)\n')
        lines.append('  // ============================================\n')
        for key in sorted(common_keys):
            value = existing_values.get(key, f"TODO: {key}")
            lines.append(f'  "{key}": "{value}",\n')
        lines.append('\n')
    
    # 모듈별 키 출력
    for module_path in sorted_modules:
        keys = keys_by_module[module_path]
        # 공통 키가 아닌 것만 출력
        module_specific_keys = keys - common_keys
        
        if module_specific_keys:
            display_name = get_module_display_name(module_path)
            # 파일 경로 추가 (예: widgets/port_settings.py)
            file_path = f"{module_path}.py"
            lines.append('  // ============================================\n')
            lines.append(f'  // {display_name} ({file_path}),\n')
            lines.append('  // ============================================\n')
            
            for key in sorted(module_specific_keys):
                value = existing_values.get(key, f"TODO: {key}")
                lines.append(f'  "{key}": "{value}",\n')
            lines.append('\n')
    
    # 마지막 쉼표 제거
    if lines[-1] == '\n':
        lines.pop()
    lines[-1] = lines[-1].rstrip(',\n') + '\n'
    
    lines.append("}\n")
    
    # 파일 쓰기 (주석 라인 제거하고 실제 JSON 생성)
    output_data = {}
    for line in lines:
        # 주석이 아닌 라인만 파싱
        if not line.strip().startswith('"//'):
            continue
    
    # 실제로는 정상 JSON으로 저장 (주석은 키로 포함)
    output_path = Path(output_file)
    output_path.write_text(''.join(lines), encoding='utf-8')
    
    print(f"✓ 템플릿 파일 생성: {output_file}")
    print(f"  - 공통 키: {len(common_keys)}개")
    print(f"  - 모듈별 키: {sum(len(keys - common_keys) for keys in keys_by_module.values())}개")

def check_missing_and_unused():
    """누락되거나 사용되지 않는 키를 확인"""
    root_dir = Path(__file__).parent.parent
    view_dir = root_dir / "view"
    used_keys = set()
    
    for py_file in view_dir.rglob("*.py"):
        content = py_file.read_text(encoding='utf-8')
        matches = re.findall(r'get_text\(["\']([^"\']+)["\']\)', content)
        used_keys.update(matches)
    
    # JSON 파일의 키들 읽기
    en_json = root_dir / "config/languages/en.json"
    ko_json = root_dir / "config/languages/ko.json"
    
    en_keys = set(json.loads(en_json.read_text(encoding='utf-8')).keys())
    ko_keys = set(json.loads(ko_json.read_text(encoding='utf-8')).keys())
    
    # 비교
    print("\n=== 누락된 키 확인 ===")
    missing_in_en = used_keys - en_keys
    missing_in_ko = used_keys - ko_keys
    
    if missing_in_en:
        print(f"\n❌ en.json에 없는 키 ({len(missing_in_en)}개):")
        for key in sorted(missing_in_en):
            print(f"  - {key}")
    else:
        print("\n✓ en.json: 모든 키가 존재합니다!")
    
    if missing_in_ko:
        print(f"\n❌ ko.json에 없는 키 ({len(missing_in_ko)}개):")
        for key in sorted(missing_in_ko):
            print(f"  - {key}")
    else:
        print("\n✓ ko.json: 모든 키가 존재합니다!")
    
    print("\n=== 사용되지 않는 키 확인 ===")
    unused = (en_keys | ko_keys) - used_keys
    
    if unused:
        print(f"\n⚠ 사용되지 않는 키 ({len(unused)}개):")
        for key in sorted(unused):
            print(f"  - {key}")
    else:
        print("\n✓ 모든 키가 사용되고 있습니다!")
    
    print(f"\n=== 통계 ===")
    print(f"코드에서 사용: {len(used_keys)}개")
    print(f"en.json: {len(en_keys)}개")
    print(f"ko.json: {len(ko_keys)}개")

def main():
    """메인 함수"""
    print("=" * 60)
    print("언어 키 관리 도구")
    print("=" * 60)
    
    # 1. 모듈별 키 추출
    print("\n[1] 모듈별 키 추출 중...")
    keys_by_module = extract_keys_by_module()
    print(f"✓ {len(keys_by_module)}개 모듈에서 키 추출 완료")
    
    # 2. 템플릿 생성
    print("\n[2] 언어 템플릿 생성 중...")
    generate_template(
        keys_by_module,
        "config/languages/template_en.json",
        "en"
    )
    
    # 3. 누락/미사용 키 확인
    print("\n[3] 키 검증 중...")
    check_missing_and_unused()
    
    print("\n" + "=" * 60)
    print("완료!")
    print("=" * 60)

if __name__ == "__main__":
    main()
