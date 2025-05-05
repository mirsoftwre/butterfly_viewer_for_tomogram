#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Butterfly Viewer 패키징 스크립트

이 스크립트는 PyInstaller를 사용하여 Butterfly Viewer 응용 프로그램을 패키징합니다.
필요한 모든 DLL 파일과 리소스를 포함한 독립 실행 파일을 생성합니다.
"""

import os
import sys
import shutil
import subprocess
import site
from pathlib import Path

# 스크립트가 있는 디렉토리를 기준으로 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUTTERFLY_DIR = os.path.join(BASE_DIR, 'butterfly_viewer')
DIST_DIR = os.path.join(BASE_DIR, 'dist')
OUTPUT_DIR = os.path.join(DIST_DIR, 'butterfly_viewer')
ICON_PATH = os.path.join(BUTTERFLY_DIR, 'icons', 'icon.ico')
MAIN_PY = os.path.join(BUTTERFLY_DIR, 'butterfly_viewer.py')

# PyInstaller 명령 및 옵션
PYINSTALLER_CMD = [
    'pyinstaller',
    '--onedir',                 # 하나의 디렉토리에 모든 파일 포함
    '--noconfirm',              # 기존 결과 디렉토리 덮어쓰기
    '--clean',                  # 빌드 전 캐시 제거
    '--name=butterfly_viewer',  # 출력 패키지 이름
    '--windowed',               # GUI 애플리케이션 (콘솔 창 없음)
    '--icon=' + ICON_PATH,      # 응용 프로그램 아이콘
    '--add-data=butterfly_viewer/icons;icons',  # 아이콘 리소스 포함
    # PyQt5가 자동으로 감지되지 않을 경우 명시적으로 포함
    '--hidden-import=PyQt5',
    '--hidden-import=PyQt5.QtCore',
    '--hidden-import=PyQt5.QtGui',
    '--hidden-import=PyQt5.QtWidgets',
    '--hidden-import=PyQt5.sip',
    # 추가 모듈들
    '--hidden-import=PIL',
    '--hidden-import=PIL.Image',
    '--hidden-import=piexif',  # EXIF 정보 처리 모듈
    MAIN_PY
]

def find_qt_binaries():
    """PyQt5의 Qt 바이너리 경로를 찾습니다."""
    try:
        import PyQt5
        qt_dir = os.path.join(os.path.dirname(PyQt5.__file__), 'Qt5', 'bin')
        
        if os.path.exists(qt_dir):
            return qt_dir
        
        # 다른 가능한 경로들 탐색
        site_packages = site.getsitepackages()
        for path in site_packages:
            qt_dir = os.path.join(path, 'PyQt5', 'Qt5', 'bin')
            if os.path.exists(qt_dir):
                return qt_dir
                
        # venv 환경에서의 경로 탐색
        venv_path = os.path.join(BASE_DIR, 'venv', 'Lib', 'site-packages', 'PyQt5', 'Qt5', 'bin')
        if os.path.exists(venv_path):
            return venv_path
            
        print("경고: PyQt5 Qt 바이너리 경로를 찾을 수 없습니다.")
        return None
    except ImportError:
        print("경고: PyQt5가 설치되어 있지 않습니다.")
        return None

def copy_qt_dlls(target_dir):
    """필요한 Qt DLL 파일을 대상 디렉토리에 복사합니다."""
    qt_bin_dir = find_qt_binaries()
    if not qt_bin_dir:
        print("Qt DLL 파일을 복사할 수 없습니다.")
        return False
    
    # 필수 Qt DLL 파일 목록
    essential_dlls = [
        'Qt5Core.dll',
        'Qt5Gui.dll',
        'Qt5Widgets.dll',
        'Qt5Svg.dll',
        'Qt5Network.dll',
        'Qt5Xml.dll',
        'Qt5PrintSupport.dll',
        'libGLESv2.dll',
        'libEGL.dll',
        'd3dcompiler_47.dll',
        'opengl32sw.dll',
    ]
    
    # 추가 DLL 목록 (필요한 경우)
    additional_dlls = [
        'Qt5MultimediaWidgets.dll',
        'Qt5Multimedia.dll',
        'Qt5Quick.dll',
        'Qt5Qml.dll',
        'Qt5QmlModels.dll',
        'vcruntime140.dll',
        'vcruntime140_1.dll',
        'msvcp140.dll',
        'msvcp140_1.dll',
        'msvcp140_2.dll',
        'concrt140.dll',
    ]
    
    # 모든 필수 DLL 파일을 대상 디렉토리에 복사
    os.makedirs(target_dir, exist_ok=True)
    success = True
    
    # 필수 DLL 복사
    for dll in essential_dlls:
        src_path = os.path.join(qt_bin_dir, dll)
        if os.path.exists(src_path):
            try:
                shutil.copy2(src_path, target_dir)
                print(f"복사됨: {dll}")
            except Exception as e:
                print(f"오류: {dll} 복사 실패 - {e}")
                success = False
        else:
            print(f"경고: {dll}를 찾을 수 없습니다.")
    
    # 추가 DLL 복사 (있는 경우만)
    for dll in additional_dlls:
        src_path = os.path.join(qt_bin_dir, dll)
        if os.path.exists(src_path):
            try:
                shutil.copy2(src_path, target_dir)
                print(f"복사됨 (추가): {dll}")
            except Exception as e:
                print(f"오류: {dll} 복사 실패 - {e}")
    
    return success

def copy_qt_plugins(qt_bin_dir, target_dir):
    """Qt 플러그인을 대상 디렉토리에 복사합니다."""
    if not qt_bin_dir:
        return False
    
    # 상위 Qt 디렉토리 찾기
    qt_dir = os.path.dirname(qt_bin_dir)
    qt_plugins_dir = os.path.join(qt_dir, 'plugins')
    
    if not os.path.exists(qt_plugins_dir):
        print(f"경고: Qt 플러그인 디렉토리를 찾을 수 없습니다: {qt_plugins_dir}")
        return False
    
    # 필요한 플러그인 디렉토리 목록
    plugin_dirs = [
        'platforms',
        'imageformats',
        'styles',
        'iconengines'
    ]
    
    # 플러그인 복사
    for plugin_dir in plugin_dirs:
        src_dir = os.path.join(qt_plugins_dir, plugin_dir)
        dst_dir = os.path.join(target_dir, plugin_dir)
        
        if os.path.exists(src_dir):
            try:
                if os.path.exists(dst_dir):
                    shutil.rmtree(dst_dir)
                shutil.copytree(src_dir, dst_dir)
                print(f"복사됨: {plugin_dir} 플러그인")
            except Exception as e:
                print(f"오류: {plugin_dir} 플러그인 복사 실패 - {e}")
                return False
        else:
            print(f"경고: {plugin_dir} 플러그인 디렉토리를 찾을 수 없습니다.")
    
    return True

def copy_icon_resources():
    """아이콘 리소스 파일을 대상 디렉토리에 복사합니다."""
    src_icons_dir = os.path.join(BUTTERFLY_DIR, 'icons')
    dst_icons_dir = os.path.join(OUTPUT_DIR, 'icons')
    
    if not os.path.exists(src_icons_dir):
        print(f"경고: 아이콘 디렉토리를 찾을 수 없습니다: {src_icons_dir}")
        return False
    
    try:
        if os.path.exists(dst_icons_dir):
            shutil.rmtree(dst_icons_dir)
        shutil.copytree(src_icons_dir, dst_icons_dir)
        print("아이콘 리소스가 성공적으로 복사되었습니다.")
        return True
    except Exception as e:
        print(f"오류: 아이콘 리소스 복사 실패 - {e}")
        return False

def create_qt_conf():
    """Qt 설정 파일을 생성합니다."""
    qt_conf_path = os.path.join(OUTPUT_DIR, 'qt.conf')
    
    try:
        with open(qt_conf_path, 'w') as f:
            f.write("[Paths]\n")
            f.write("Prefix = .\n")
            f.write("Binaries = .\n")
            f.write("Libraries = .\n")
            f.write("Plugins = .\n")
        print("qt.conf 파일이 성공적으로 생성되었습니다.")
        return True
    except Exception as e:
        print(f"오류: qt.conf 파일 생성 실패 - {e}")
        return False

def run_pyinstaller():
    """PyInstaller를 실행하여 애플리케이션을 패키징합니다."""
    print("=" * 70)
    print("PyInstaller로 Butterfly Viewer 패키징 시작...")
    print("=" * 70)
    
    # PyInstaller 명령 실행
    try:
        result = subprocess.run(PYINSTALLER_CMD, check=True)
        print("\nPyInstaller 실행 완료!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"오류: PyInstaller 실행 실패 - {e}")
        return False
    except Exception as e:
        print(f"오류: {e}")
        return False

def process_dist_directory():
    """dist 디렉토리를 처리하고 필요한 파일을 확인합니다."""
    # dist 디렉토리에서 생성된 디렉토리 확인
    if not os.path.exists(OUTPUT_DIR):
        print(f"오류: 출력 디렉토리를 찾을 수 없습니다: {OUTPUT_DIR}")
        return False
    
    # 생성된 실행 파일 확인
    exe_path = os.path.join(OUTPUT_DIR, 'butterfly_viewer.exe')
    if not os.path.exists(exe_path):
        print(f"오류: 생성된 실행 파일을 찾을 수 없습니다: {exe_path}")
        return False
    
    print(f"생성된 실행 파일 확인: {exe_path} (크기: {os.path.getsize(exe_path)/1024:.1f} KB)")
    return True

def find_module_paths():
    """필요한 Python 모듈들의 경로를 찾습니다."""
    module_paths = {}
    
    try:
        # NumPy 경로 찾기
        import numpy
        module_paths['numpy'] = os.path.dirname(numpy.__file__)
    except ImportError:
        print("경고: NumPy가 설치되어 있지 않습니다.")
    
    try:
        # PIL/Pillow 경로 찾기
        import PIL
        module_paths['PIL'] = os.path.dirname(PIL.__file__)
    except ImportError:
        print("경고: PIL/Pillow가 설치되어 있지 않습니다.")
        
    try:
        # piexif 경로 찾기
        import piexif
        module_paths['piexif'] = os.path.dirname(piexif.__file__)
    except ImportError:
        print("경고: piexif가 설치되어 있지 않습니다.")
    
    try:
        # pywin32 관련 경로 찾기
        import win32com
        module_paths['win32com'] = os.path.dirname(win32com.__file__)
        
        import win32api
        module_paths['win32'] = os.path.dirname(win32api.__file__)
        
        import pythoncom
        module_paths['pythoncom'] = os.path.dirname(pythoncom.__file__)
    except ImportError:
        print("경고: pywin32가 설치되어 있지 않거나 일부 모듈을 찾을 수 없습니다.")
    
    # 이미지에 pystdlib가 보이지만 실제로는 존재하지 않을 수 있음
    # 시스템에 설치되어 있는 경우에만 포함
    try:
        # pystdlib 경로 찾기 시도
        import pystdlib
        module_paths['pystdlib'] = os.path.dirname(pystdlib.__file__)
    except ImportError:
        # 오류 출력 없이 건너뜀
        pass
    
    return module_paths

def copy_additional_modules(target_dir):
    """추가 모듈 파일들을 대상 디렉토리에 복사합니다."""
    module_paths = find_module_paths()
    
    if not module_paths:
        print("추가 모듈 파일을 복사할 수 없습니다.")
        return False
    
    # NumPy DLL 복사
    if 'numpy' in module_paths:
        numpy_path = module_paths['numpy']
        numpy_dll_path = os.path.join(numpy_path, 'core')
        
        if os.path.exists(numpy_dll_path):
            try:
                # NumPy 디렉토리 복사
                numpy_target = os.path.join(target_dir, 'numpy')
                if not os.path.exists(numpy_target):
                    os.makedirs(numpy_target, exist_ok=True)
                
                # DLL 복사
                for item in os.listdir(numpy_dll_path):
                    if item.endswith('.dll'):
                        src_file = os.path.join(numpy_dll_path, item)
                        dst_file = os.path.join(target_dir, item)
                        shutil.copy2(src_file, dst_file)
                        print(f"복사됨 (NumPy): {item}")
            except Exception as e:
                print(f"오류: NumPy 파일 복사 실패 - {e}")
    
    # PIL DLL 복사
    if 'PIL' in module_paths:
        pil_path = module_paths['PIL']
        
        try:
            # PIL DLL 파일 탐색 및 복사
            for item in os.listdir(pil_path):
                if item.endswith('.dll'):
                    src_file = os.path.join(pil_path, item)
                    dst_file = os.path.join(target_dir, item)
                    shutil.copy2(src_file, dst_file)
                    print(f"복사됨 (PIL): {item}")
        except Exception as e:
            print(f"오류: PIL 파일 복사 실패 - {e}")
    
    # piexif 모듈 복사
    if 'piexif' in module_paths:
        piexif_path = module_paths['piexif']
        
        try:
            # piexif 디렉토리 복사
            piexif_target = os.path.join(target_dir, 'piexif')
            if not os.path.exists(piexif_target):
                os.makedirs(piexif_target, exist_ok=True)
            
            # 모든 .py 파일 복사
            for item in os.listdir(piexif_path):
                if item.endswith('.py') or item.endswith('.pyc') or item.endswith('.pyd'):
                    src_file = os.path.join(piexif_path, item)
                    if os.path.isfile(src_file):
                        dst_file = os.path.join(piexif_target, item)
                        shutil.copy2(src_file, dst_file)
                        print(f"복사됨 (piexif): {item}")
        except Exception as e:
            print(f"오류: piexif 파일 복사 실패 - {e}")
    
    # pywin32 관련 파일 복사
    for module_name in ['win32', 'win32com', 'pythoncom']:
        if module_name in module_paths:
            module_path = module_paths[module_name]
            
            try:
                # DLL 파일 탐색 및 복사
                if module_name == 'win32':
                    # win32 모듈 디렉토리에서 DLL 찾기
                    for item in os.listdir(module_path):
                        if item.endswith('.dll') or item.endswith('.pyd'):
                            src_file = os.path.join(module_path, item)
                            dst_file = os.path.join(target_dir, item)
                            shutil.copy2(src_file, dst_file)
                            print(f"복사됨 (win32): {item}")
                
                # pythoncom DLL 복사
                if module_name == 'pythoncom':
                    pythoncom_path = module_paths['pythoncom']
                    parent_dir = os.path.dirname(pythoncom_path)
                    
                    for item in os.listdir(parent_dir):
                        if item.startswith('pythoncom') and (item.endswith('.dll') or item.endswith('.pyd')):
                            src_file = os.path.join(parent_dir, item)
                            dst_file = os.path.join(target_dir, item)
                            shutil.copy2(src_file, dst_file)
                            print(f"복사됨 (pythoncom): {item}")
                    
                    # pywintypes DLL도 복사
                    for item in os.listdir(parent_dir):
                        if item.startswith('pywintypes') and (item.endswith('.dll') or item.endswith('.pyd')):
                            src_file = os.path.join(parent_dir, item)
                            dst_file = os.path.join(target_dir, item)
                            shutil.copy2(src_file, dst_file)
                            print(f"복사됨 (pywintypes): {item}")
            except Exception as e:
                print(f"오류: {module_name} 파일 복사 실패 - {e}")
    
    # pystdlib 파일 복사
    if 'pystdlib' in module_paths:
        pystdlib_path = module_paths['pystdlib']
        
        try:
            # DLL 파일 탐색 및 복사
            for item in os.listdir(pystdlib_path):
                if item.endswith('.dll') or item.endswith('.pyd'):
                    src_file = os.path.join(pystdlib_path, item)
                    dst_file = os.path.join(target_dir, item)
                    shutil.copy2(src_file, dst_file)
                    print(f"복사됨 (pystdlib): {item}")
        except Exception as e:
            print(f"오류: pystdlib 파일 복사 실패 - {e}")
    
    return True

def main():
    """빌드 스크립트의 메인 함수"""
    # 현재 디렉토리를 프로젝트 루트로 변경
    os.chdir(BASE_DIR)
    
    # PyInstaller 실행
    if not run_pyinstaller():
        print("패키징 실패: PyInstaller 실행 오류")
        return False
    
    # 출력 디렉토리 확인
    if not process_dist_directory():
        print("패키징 실패: 출력 디렉토리 처리 오류")
        return False
    
    # Qt DLL 파일 복사
    qt_bin_dir = find_qt_binaries()
    if not copy_qt_dlls(OUTPUT_DIR):
        print("패키징 실패: Qt DLL 복사 오류")
        return False
    
    # Qt 플러그인 복사
    if not copy_qt_plugins(qt_bin_dir, OUTPUT_DIR):
        print("패키징 실패: Qt 플러그인 복사 오류")
        return False
    
    # 추가 모듈 파일 복사
    if not copy_additional_modules(OUTPUT_DIR):
        print("경고: 일부 추가 모듈 파일 복사 오류가 발생했습니다.")
    
    # 아이콘 리소스 복사
    if not copy_icon_resources():
        print("패키징 실패: 아이콘 리소스 복사 오류")
        return False
    
    # Qt 설정 파일 생성
    if not create_qt_conf():
        print("패키징 실패: Qt 설정 파일 생성 실패")
        return False
    
    print("\n" + "=" * 70)
    print(f"패키징 완료! 결과물 위치: {OUTPUT_DIR}")
    print("=" * 70)
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1) 