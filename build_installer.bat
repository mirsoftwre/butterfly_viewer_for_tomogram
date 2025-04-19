@echo off
echo Butterfly Viewer 설치 프로그램 빌드 스크립트
echo ====================================================

REM NSIS 경로 확인
set NSIS_PATH="C:\Program Files (x86)\NSIS\makensis.exe"
if not exist %NSIS_PATH% (
    set NSIS_PATH="C:\Program Files\NSIS\makensis.exe"
)

if not exist %NSIS_PATH% (
    echo NSIS가 설치되어 있지 않거나 기본 경로에 없습니다.
    echo NSIS를 설치하거나 경로를 수동으로 지정해주세요.
    goto :end
)

REM 설치 파일 생성
echo NSIS를 사용하여 설치 프로그램 생성 중...
%NSIS_PATH% -INPUTCHARSET UTF8 installer.nsi

if %ERRORLEVEL% NEQ 0 (
    echo 설치 프로그램 생성 중 오류가 발생했습니다.
    goto :end
) else (
    echo 설치 프로그램이 성공적으로 생성되었습니다: Butterfly_Viewer_Setup.exe
)

:end
pause 