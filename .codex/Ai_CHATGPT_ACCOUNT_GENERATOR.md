# AI Notes

## User Goal
`Chatgpt_Account_Generator` 프로젝트의 문서를 현재 코드 구조와 맞게 정리한다.

## Current Scope
- 사용자용 한국어 README를 정리한다.
- 개발자용 한국어 상세 문서를 추가한다.
- 프로젝트의 핵심 모듈, 실행 방식, 설정값, 저장 파일을 문서화한다.

## Relevant Files and Modules
- `main.py`: 웹/CLI 진입점, 로그 초기화
- `backend/cli.py`: CLI 메뉴 및 계정 생성/내보내기 흐름
- `backend/service.py`: 계정 생성 오케스트레이션
- `backend/config.py`: 환경 변수와 경로 정의
- `backend/storage.py`: 계정/이메일 DB 저장, 백업, 삭제
- `frontend/app.py`: Flask 웹 UI 및 작업 상태 표시
- `backend/account_verification.py`: 계정 검증
- `backend/jobs.py`: 웹 작업 상태 저장

## Core Business Logic
- 계정 생성은 `create_account_generator`로 이메일을 만들고, OTP 대기를 거쳐 `register_account`로 등록을 마치는 흐름이다.
- OTP는 로컬 Mailcow IMAP에서 조회한다.
- 성공한 계정은 `data/accounts.json`과 `data/email-db.json`에 저장된다.
- 중복 이메일은 `is_email_used()`로 차단한다.
- 저장 시 백업 JSON을 `data/backups/`에 남기고 보관 수는 `BACKUP_KEEP_LIMIT`으로 제한한다.
- 실행 시 `main.py`가 stdout/stderr를 `logs/latest.log`로 tee 한다.

## Architecture and Data Flow
- `main.py`
  - 실행 모드에 따라 Flask 웹 UI 또는 CLI를 시작한다.
  - 시작 시 로그 파일을 초기화하고 표준 출력을 함께 기록한다.
- `backend/cli.py`
  - 사용자의 입력을 받아 생성 수와 suffix를 설정한다.
  - `backend.service.create_accounts()` 또는 `export_accounts()`를 호출한다.
- `backend/service.py`
  - 이메일 생성 -> 중복 검사 -> 등록 -> OTP 확인 -> 저장 순으로 계정을 처리한다.
  - 결과 집계와 진행 로그를 담당한다.
- `backend/storage.py`
  - 파일 저장 전 백업을 만들고, 계정/이메일 DB를 갱신한다.
- `frontend/app.py`
  - 웹 UI 작업 상태를 계산해 사용자에게 단계별 진행 정보를 보여준다.

## Important Facts
- 프로젝트는 Python 기반이며 Flask 웹 UI와 CLI를 함께 제공한다.
- 기존 README는 모듈 이름과 실제 구조가 일부 어긋날 수 있으므로, 현재 코드 기준으로 재정리한다.
- `backend/account_creation/` 경로는 현재 확인된 파일 목록과 맞지 않으므로 문서에서 실제 존재하는 파일 위주로 설명해야 한다.
- 주요 저장 파일은 `data/accounts.json`, `data/email-db.json`, `data/jobs.json`, `data/result.txt`, `logs/latest.log`, `logs/latest-imap.eml`이다.

## Next Steps
- 사용자용 `README_KO.md`를 프로젝트 실제 동작 기준으로 개편한다.
- 개발자용 `README_DEV_KO.md`를 추가해 설정값과 흐름을 더 자세히 설명한다.
- 필요하면 영어 README도 별도로 추가할 수 있다.

