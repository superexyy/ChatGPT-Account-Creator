[English](#english) | [한국어](#korean)

<a name="english"></a>
# ChatGPT Account Generator

This project is a Python-based automation tool that generates email accounts, waits for OTP mail in a local Mailcow IMAP mailbox, and completes registration.
It supports both a web UI and a CLI, and stores results in local JSON files.

## What it does

- Account generation
- OTP mail lookup
- Account registration
- Account verification
- Result persistence and backups
- Web UI progress tracking
- CLI-based execution

## What you need

- Python installed on your computer
- This project folder
- Access to the mail system used for OTP

## Easy start

1. Open the project folder.
2. Install the needed files.

```bash
pip install -r requirements.txt
```

3. Start the app.

```bash
python main.py
```

4. If you want the text-only version, use this instead:

```bash
python main.py cli
```

## Simple usage

1. Enter how many accounts you want.
2. If needed, add a short email suffix.
3. Let the program make the account data.
4. Wait for the OTP mail.
5. Confirm the OTP.
6. Save or export the result.

## Saved files

- `data/accounts.json`
- `data/email-db.json`
- `data/jobs.json`
- `data/result.txt`
- `data/backups/`
- `logs/latest.log`
- `logs/latest-imap.eml`
- `logs/resend-post.log`

## Settings

If you need to change the mail connection or waiting time, copy `.env.example` to `.env`.
Most people can keep the default values.

## Notes

- This project saves data on your computer.
- Results are written in a simple file format.
- Backup copies are made automatically.

<a name="korean"></a>
# ChatGPT Account Generator

이 프로젝트는 이메일 계정을 생성하고, 로컬 Mailcow IMAP 메일함에서 OTP 메일을 확인해 등록을 완료하는 Python 기반 자동화 도구입니다.
웹 UI와 CLI를 모두 제공하며, 생성 결과는 로컬 JSON 파일에 저장됩니다.

## 할 수 있는 일

- 이메일 계정 생성
- OTP 메일 조회
- 계정 등록
- 계정 검증
- 결과 저장 및 백업
- 웹 UI 작업 상태 표시
- CLI 기반 실행

## 준비물

- 컴퓨터에 설치된 Python
- 이 프로젝트 폴더
- OTP에 사용하는 메일 시스템 접근 권한

## 시작 방법

1. 프로젝트 폴더를 엽니다.
2. 필요한 파일을 설치합니다.

```bash
pip install -r requirements.txt
```

3. 앱을 실행합니다.

```bash
python main.py
```

4. 텍스트 전용 버전을 원하면 다음을 사용합니다.

```bash
python main.py cli
```

## 사용 방법

1. 생성할 계정 수를 입력합니다.
2. 필요하면 짧은 email suffix를 추가합니다.
3. 프로그램이 계정 데이터를 만들도록 둡니다.
4. OTP 메일을 기다립니다.
5. OTP를 확인합니다.
6. 결과를 저장하거나 내보냅니다.

## 저장되는 파일

- `data/accounts.json`
- `data/email-db.json`
- `data/jobs.json`
- `data/result.txt`
- `data/backups/`
- `logs/latest.log`
- `logs/latest-imap.eml`
- `logs/resend-post.log`

## 설정

메일 연결 정보나 대기 시간을 바꿔야 하면 `.env.example`을 `.env`로 복사합니다.
대부분의 사용자는 기본값을 그대로 사용해도 됩니다.

## 참고

- 이 프로젝트는 데이터를 컴퓨터에 저장합니다.
- 결과는 단순한 파일 형식으로 기록됩니다.
- 백업 복사본은 자동으로 만들어집니다.
