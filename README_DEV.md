[English](#english) | [한국어](#korean)

<a name="english"></a>
# ChatGPT Account Generator - Developer Guide

This document explains the internal structure and runtime behavior of `Chatgpt_Account_Generator` for developers.

## Project Goal

The project is a Python-based automation tool that generates email accounts, waits for OTP mail in a local Mailcow IMAP mailbox, and completes registration.
It supports both a web UI and a CLI, and stores results in local JSON files.

## Scope

- Account generation
- OTP mail lookup
- Account registration
- Account verification
- Result persistence and backups
- Web UI progress tracking
- CLI-based execution

## Directory Layout

- `main.py`: entry point
- `backend/`
  - `cli.py`: CLI menu and input handling
  - `service.py`: account generation orchestration
  - `config.py`: environment variables and paths
  - `storage.py`: JSON persistence, deduplication, backup, delete
  - `jobs.py`: web job state
  - `account_verification.py`: verification flow
  - `http_client.py`: HTTP request helpers
  - `quota.py`: quota-related logic
  - `debug_log.py`: debug logging helpers
  - `account_creation/`: email generation, OTP waiting, registration
- `frontend/`
  - `app.py`: Flask app, routes, progress computation
  - `i18n.py`: localization helpers
  - `webui/`: templates and static UI assets
- `data/`: results, email DB, job state, backups
- `logs/`: runtime logs and debug output
- `.env`: runtime configuration

## Runtime Flow

### 1. Startup

`main.py` tees `stdout` and `stderr` into `logs/latest.log`.
The default mode is the web UI; passing `cli` starts the CLI.

### 2. Email Generation

`backend.service.create_accounts()` creates account payloads via `create_account_generator()`.
If a suffix is provided, it is appended to the local part of the email address.

### 3. Deduplication

`backend.storage.is_email_used()` checks both `data/email-db.json` and `data/accounts.json`.
Already used emails are skipped before registration.

### 4. OTP Waiting

`create_otp_waiter()` polls the local Mailcow IMAP mailbox for OTP mail.
Timeout and polling frequency are controlled by `OTP_TIMEOUT` and `OTP_POLL`.

### 5. Registration

`register_account()` performs the registration request.
Progress logs include account numbers and email addresses so the UI can show meaningful progress.

### 6. Persistence

Successful accounts are saved through `save_account()` and `save_email_to_db()`.
Backups are created before file writes and are pruned according to `BACKUP_KEEP_LIMIT`.

## Data Flow

### Inputs

- `.env`
- CLI input
- web UI requests
- Mailcow IMAP mailbox

### Processing

- email generation
- deduplication
- OTP waiting
- registration
- verification

### Outputs

- `data/accounts.json`
- `data/email-db.json`
- `data/result.txt`
- `data/jobs.json`
- `logs/latest.log`
- `logs/latest-imap.eml`
- `logs/resend-post.log`

## Core Logic

### `backend/service.py`

- This is the orchestration layer for account creation.
- Success is determined by the presence of `accessToken`, `userId`, and `email`.
- It accepts an optional logger callback for progress output.

### `backend/storage.py`

- Creates backups before writes.
- Prevents duplicate email storage.
- Handles account field updates and deletion.

### `frontend/app.py`

- Converts job logs into human-readable progress text.
- Progress calculation differs by job type.
- Separates account creation and verification status display.

### `backend/cli.py`

- Provides a menu-driven interface.
- Collects account count and suffix input.
- Prints export results.

## Configuration

Values loaded from `backend/config.py`:

- `BATCH_SIZE`
- `OTP_TIMEOUT`
- `OTP_POLL`
- `EMAIL_DOMAINS`
- `MAILCOW_IMAP_HOST`
- `MAILCOW_IMAP_PORT`
- `MAILCOW_IMAP_SSL`
- `MAILCOW_IMAP_USERNAME`
- `MAILCOW_IMAP_PASSWORD`
- `MAILCOW_IMAP_MAILBOX`
- `MAILCOW_IMAP_SCAN_LIMIT`
- `MAILCOW_IMAP_LOG_LIMIT`
- `BACKUP_KEEP_LIMIT`
- `CHATGPT_QUOTA_URL`

## Implementation Notes

- The `account_creation/` implementation should be documented according to the actual files that exist in the repository.
- Backup files are created frequently during writes, so code and docs must stay aligned with that policy.
- Web UI status messages rely heavily on log message strings, so log wording changes may require UI updates.
- `main.py` opens a fresh log file on every run.
- When troubleshooting failures, check both the logs and job state to identify the last successful step.

## Important Facts

- This is a Python implementation.
- It supports both web UI and CLI workflows.
- OTP comes from a local Mailcow IMAP mailbox, not from an external mail API.
- Results are stored in JSON and duplicate emails are rejected before persistence.
- Parts of the previous README may not match the current code structure.

## Future Work

- Keep the README and developer guide aligned with the codebase.
- Inspect the actual files under `backend/account_creation/` if more detail is needed.
- Provide a separate English document set where appropriate.
- Update this documentation whenever routes or CLI behavior changes.

<a name="korean"></a>
# ChatGPT Account Generator - 개발자 가이드

이 문서는 `Chatgpt_Account_Generator`의 내부 동작과 파일 구조를 개발자 기준으로 설명합니다.

## 프로젝트 목표

이 프로젝트는 Python 기반으로 이메일 계정을 생성하고, OTP 메일을 로컬 Mailcow IMAP에서 확인해 등록을 완료하는 자동화 도구입니다.
웹 UI와 CLI를 모두 제공하며, 생성 결과는 로컬 JSON 파일에 저장됩니다.

## 현재 범위

- 이메일 계정 생성
- OTP 메일 조회
- 계정 등록
- 계정 검증
- 결과 저장 및 백업
- 웹 UI 작업 상태 표시
- CLI 기반 수동 실행

## 디렉터리 구조

- `main.py`: 실행 진입점
- `backend/`
  - `cli.py`: CLI 메뉴와 사용자 입력 처리
  - `service.py`: 계정 생성 오케스트레이션
  - `config.py`: 환경 변수와 경로 상수
  - `storage.py`: JSON 저장, 중복 검사, 백업, 삭제
  - `jobs.py`: 웹 UI 작업 상태 저장
  - `account_verification.py`: 계정 검증 로직
  - `http_client.py`: HTTP 요청 보조
  - `quota.py`: quota 조회 관련 로직
  - `debug_log.py`: 디버그 로그 관련 기능
  - `account_creation/`: 이메일 생성, OTP 대기, 등록 구현
- `frontend/`
  - `app.py`: Flask 앱, 라우트, 진행 상태 계산
  - `i18n.py`: 다국어 지원
  - `webui/`: 템플릿과 정적 화면
- `data/`: 계정 결과, 이메일 DB, 작업 상태, 백업
- `logs/`: 실행 로그와 디버그 산출물
- `.env`: 실행 설정

## 실행 흐름

### 1. 초기화

`main.py`는 실행 시 `stdout`와 `stderr`를 `logs/latest.log`로 함께 기록한다.
웹 모드가 기본이며, `cli` 인자가 오면 CLI를 실행한다.

### 2. 이메일 생성

`backend.service.create_accounts()`는 `create_account_generator()`를 통해 계정을 생성한다.
필요하면 suffix를 붙여 이메일 주소를 수정한다.

### 3. 중복 검사

`backend.storage.is_email_used()`가 `data/email-db.json`과 `data/accounts.json`을 확인한다.
이미 사용한 이메일이면 해당 계정은 건너뛴다.

### 4. OTP 대기

`create_otp_waiter()`가 Mailcow IMAP을 폴링해 OTP 메일을 찾는다.
대기 시간과 폴링 간격은 `OTP_TIMEOUT`, `OTP_POLL`로 제어한다.

### 5. 등록

`register_account()`가 등록 요청을 수행한다.
진행 로그는 계정 번호와 이메일을 포함해 기록된다.

### 6. 저장

성공한 계정은 `save_account()`와 `save_email_to_db()`를 통해 저장된다.
저장 전에는 `data/backups/`에 백업이 생성되며, 보관 수는 `BACKUP_KEEP_LIMIT`으로 제한된다.

## 데이터 흐름

### 입력

- `.env`
- 사용자 CLI 입력
- 웹 UI 요청
- Mailcow IMAP 메일함

### 처리

- 이메일 생성
- 중복 검사
- OTP 수신 대기
- 등록 완료
- 계정 검증

### 출력

- `data/accounts.json`
- `data/email-db.json`
- `data/result.txt`
- `data/jobs.json`
- `logs/latest.log`
- `logs/latest-imap.eml`
- `logs/resend-post.log`

## 핵심 로직

### `backend/service.py`

- 계정 생성의 중심 오케스트레이터다.
- 성공 여부는 `accessToken`, `userId`, `email` 존재 여부로 판단한다.
- 작업 로그를 외부 logger 콜백으로 전달할 수 있다.

### `backend/storage.py`

- 파일 저장 전 백업을 만든다.
- 이메일 중복을 방지한다.
- 계정 필드 갱신과 삭제를 담당한다.

### `frontend/app.py`

- 작업 상태를 사람이 읽기 쉬운 문장으로 변환한다.
- 진행률 계산은 작업 종류에 따라 다르게 처리한다.
- 계정 생성과 검증 작업을 분리해서 표시한다.

### `backend/cli.py`

- 메뉴 기반 인터페이스를 제공한다.
- 생성 수와 suffix를 입력받아 서비스를 호출한다.
- 내보내기 결과를 출력한다.

## 설정 값

`backend/config.py`에서 로드하는 값:

- `BATCH_SIZE`
- `OTP_TIMEOUT`
- `OTP_POLL`
- `EMAIL_DOMAINS`
- `MAILCOW_IMAP_HOST`
- `MAILCOW_IMAP_PORT`
- `MAILCOW_IMAP_SSL`
- `MAILCOW_IMAP_USERNAME`
- `MAILCOW_IMAP_PASSWORD`
- `MAILCOW_IMAP_MAILBOX`
- `MAILCOW_IMAP_SCAN_LIMIT`
- `MAILCOW_IMAP_LOG_LIMIT`
- `BACKUP_KEEP_LIMIT`
- `CHATGPT_QUOTA_URL`

## 구현 시 주의사항

- `backend/account_creation/` 관련 구현은 현재 실제 파일 존재 여부를 기준으로 설명해야 한다.
- 저장 파일은 실행 중 백업이 계속 만들어지므로, 문서와 코드가 백업 정책에 맞는지 확인해야 한다.
- 웹 UI 상태 메시지는 로그 메시지 문자열에 의존하는 부분이 많으므로, 로그 문구 변경 시 UI 문구도 함께 점검해야 한다.
- `main.py`는 로그 파일을 매 실행마다 새로 연다.
- 실패 상황에서 어떤 단계에서 멈췄는지 로그와 `jobs` 상태를 함께 확인해야 한다.

## 중요한 사실

- 이 프로젝트는 Python 구현이다.
- 웹 UI와 CLI가 동시에 존재한다.
- OTP는 외부 메일 서비스가 아니라 로컬 Mailcow IMAP을 사용한다.
- 결과 저장은 JSON 기반이며, 중복 이메일은 저장 전에 차단한다.
- 기존 README의 일부 경로 설명은 현재 코드와 맞지 않을 수 있다.

## 향후 작업 계획

- README와 개발자 문서를 현재 코드 기준으로 유지한다.
- 실제 존재하는 `account_creation` 구현 파일 목록을 추가로 점검한다.
- 필요하면 영어 문서를 별도로 제공한다.
- UI 라우트와 CLI 동작이 바뀌면 문서의 흐름도 즉시 갱신한다.
