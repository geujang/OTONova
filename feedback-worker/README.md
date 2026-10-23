# OTONova → Workers → Discord 피드백 포럼

## 현재 준비 상태

코드와 로컬 모의 전송 검사는 준비되어 있습니다. 실제 사용에는 개발자의 Cloudflare 계정과 Discord 봇 설정이 필요합니다. 계정·봇·Secrets·Worker URL이 없으면 포럼 게시이 연결된 것으로 표시하지 않습니다.

## 1. Cloudflare 무료 계정

[Cloudflare 가입](https://dash.cloudflare.com/sign-up) 후 이메일 인증과 로그인을 완료합니다. Workers Free를 사용합니다. 유료 플랜, 도메인 구매, KV·D1·Queues는 이 구성에 필요하지 않습니다.

## 2. Discord 봇

1. [Discord Developer Portal](https://discord.com/developers/applications)에서 New Application을 만듭니다.
2. Bot 페이지에서 봇을 생성하고 토큰을 준비합니다. 토큰은 채팅·코드·EXE에 넣지 않습니다.
3. OAuth2 URL Generator에서 `bot` 범위로 초대 URL을 만들고, 본인이 관리하는 서버에 봇을 초대합니다. 관리자 권한이나 Message Content Intent는 이 REST 전송 코드에 필요하지 않습니다.
4. 피드백 포럼 채널에서 봇에 채널 보기·메시지 보내기·메시지 기록 보기 권한을 허용합니다.
5. 개발자 모드에서 포럼 채널을 우클릭하고 **채널 ID 복사**를 선택합니다.
6. 선택적으로 `오류 제보`, `기능 제안`, `기타` 태그를 만들면 분류에 따라 적용합니다. 필수 태그를 사용하는 채널은 세 분류에 대응하는 태그가 모두 필요합니다.

## 3. Worker 배포

이 디렉터리에서 다음 명령을 실행합니다. Wrangler는 개발 도구이며 배포 EXE에 들어가지 않습니다.

```powershell
npx wrangler@4 login
npx wrangler@4 deploy
npx wrangler@4 secret put DISCORD_BOT_TOKEN
npx wrangler@4 secret put DISCORD_FORUM_CHANNEL_ID
```

두 `secret put` 명령의 입력창에 봇 토큰과 포럼 채널의 숫자 ID를 각각 입력합니다. 또는 Cloudflare 대시보드의 해당 Worker → Settings → Variables and Secrets에서 같은 이름의 Secret을 직접 추가합니다.

`wrangler.toml`의 두 Rate Limiting 바인딩도 배포되어야 합니다. 없으면 안전하게 전송을 중지합니다. 제한은 IP당 분당 6회, 전체 분당 30회이며 Cloudflare 위치별 근사 제한입니다. 정확한 하루 전송 건수를 보장하는 카운터는 아닙니다.

## 4. 앱 연결

`assets/feedback-config.json`의 `endpoint`를 배포된 HTTPS 주소로 바꿉니다.

```json
{"endpoint":"https://otonova-feedback.ACCOUNT.workers.dev/feedback"}
```

봇 토큰과 채널 ID는 앱 설정 파일에 넣지 않습니다. 개발자가 이 URL을 넣은 뒤 설치 파일을 다시 만듭니다. GitHub 업로드는 별도 지시가 있을 때만 합니다.

## 5. 실제 수신 검사

앱의 도움말 → 피드백에서 테스트 내용을 보내고, 지정한 포럼 채널에 새 게시글이 생성되는지 확인합니다. Worker는 게시글과 첫 메시지의 생성 성공을 확인한 경우에만 앱에 성공을 알립니다.

게시글 제목은 분류와 내용 첫 부분으로 구성됩니다. 본문에는 앱 버전·분류·선택 연락처·전송 식별자·내용을 넣습니다. 채널 접근 권한이 있는 서버 멤버가 볼 수 있으므로 앱에 공개 범위를 안내합니다.

실패하면 작성 내용과 전송 식별자를 로컬에 보존하며 재시도는 사용자가 누를 때만 합니다. 포럼 생성 API는 nonce 중복 방지를 지원하지 않으므로 응답 유실 후 재시도하면 중복 게시글이 생길 수 있습니다. 본문의 식별자로 중복 여부를 확인할 수 있습니다.

## 전송 데이터와 테스트

작성 내용, 선택 연락처, 분류, 앱 버전, 무작위 전송 식별자만 서버로 보냅니다. WAV·oto.ini·로그·프로젝트 경로는 보내지 않습니다. 네트워크 주소는 Cloudflare가 연결 처리 및 횟수 제한에 사용하지만 Discord 게시글에는 넣지 않습니다.

```powershell
node --test worker.test.mjs
```

Worker는 별도 데이터베이스나 영구 큐를 사용하지 않습니다. 무료 한도 또는 Discord 제한으로 실패하면 앱에 남겨 둔 내용을 나중에 다시 보내야 합니다.
