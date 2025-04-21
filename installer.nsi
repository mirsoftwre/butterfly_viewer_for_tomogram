; Butterfly Viewer 설치 프로그램 스크립트
; NSIS(Nullsoft Scriptable Install System) 스크립트

!define APPNAME "Butterfly Viewer for Volumetric Images"
!define COMPANYNAME "Mir Software"
!define DESCRIPTION "Image Viewer for Volumetrics Images"
!define VERSIONMAJOR 1
!define VERSIONMINOR 1
!define VERSIONBUILD 1
!define HELPURL "https://github.com/mirsoftwre/butterfly_viewer_for_tomogram"
!define UPDATEURL "https://github.com/mirsoftwre/butterfly_viewer_for_tomogram"
!define ABOUTURL "https://github.com/mirsoftwre/butterfly_viewer_for_tomogram"

; 윈도우용 현대적인 UI 설정
!include "MUI2.nsh"
!include "FileFunc.nsh"

; 기본 설정
Name "${APPNAME}"
OutFile "Butterfly_Viewer_V${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}_Setup.exe"
InstallDir "$PROGRAMFILES64\${APPNAME}"
InstallDirRegKey HKLM "Software\${APPNAME}" "Install_Dir"
RequestExecutionLevel admin

; 모던 인터페이스 설정
!define MUI_ABORTWARNING
!define MUI_ICON "butterfly_viewer\icons\icon.ico"
!define MUI_UNICON "butterfly_viewer\icons\icon.ico"

; 페이지 설정
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; 언인스톨 페이지
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; 언어 설정
!insertmacro MUI_LANGUAGE "Korean"
!insertmacro MUI_LANGUAGE "English"

; 설치 섹션
Section "Butterfly Viewer" SecMain

    SetOutPath "$INSTDIR"
    
    ; 모든 파일 복사
    File /r "dist\butterfly_viewer\*.*"
    
    ; 바로가기 생성
    CreateDirectory "$SMPROGRAMS\${APPNAME}"
    CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\butterfly_viewer.exe" "" "$INSTDIR\butterfly_viewer.exe" 0
    CreateShortcut "$SMPROGRAMS\${APPNAME}\Uninstall.lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\uninstall.exe" 0
    CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\butterfly_viewer.exe" "" "$INSTDIR\butterfly_viewer.exe" 0
    
    ; 레지스트리 키 작성
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayName" "${APPNAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "UninstallString" '"$INSTDIR\uninstall.exe"'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "QuietUninstallString" '"$INSTDIR\uninstall.exe" /S'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayIcon" "$INSTDIR\butterfly_viewer.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "Publisher" "${COMPANYNAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "HelpLink" "${HELPURL}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "URLUpdateInfo" "${UPDATEURL}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "URLInfoAbout" "${ABOUTURL}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayVersion" "${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "VersionMajor" ${VERSIONMAJOR}
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "VersionMinor" ${VERSIONMINOR}
    
    ; 프로그램 크기 계산 및 레지스트리에 저장
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "EstimatedSize" "$0"
    
    ; 파일 연결 등록 (.tif, .tiff 파일)
    WriteRegStr HKCR ".tif" "" "ButterflyViewer.Image"
    WriteRegStr HKCR ".tiff" "" "ButterflyViewer.Image"
    WriteRegStr HKCR "ButterflyViewer.Image" "" "Tomogram Image File"
    WriteRegStr HKCR "ButterflyViewer.Image\DefaultIcon" "" "$INSTDIR\butterfly_viewer.exe,0"
    WriteRegStr HKCR "ButterflyViewer.Image\shell\open\command" "" '"$INSTDIR\butterfly_viewer.exe" "%1"'
    
    ; 언인스톨러 작성
    WriteUninstaller "$INSTDIR\uninstall.exe"

SectionEnd

; 언인스톨 섹션
Section "Uninstall"

    ; 프로그램 파일 제거
    RMDir /r "$INSTDIR\*.*"
    RMDir "$INSTDIR"
    
    ; 바로가기 제거
    Delete "$SMPROGRAMS\${APPNAME}\*.*"
    RMDir "$SMPROGRAMS\${APPNAME}"
    Delete "$DESKTOP\${APPNAME}.lnk"
    
    ; 레지스트리 키 제거
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"
    DeleteRegKey HKLM "Software\${APPNAME}"
    
    ; 파일 연결 제거
    DeleteRegKey HKCR ".tif"
    DeleteRegKey HKCR ".tiff"
    DeleteRegKey HKCR "ButterflyViewer.Image"

SectionEnd 