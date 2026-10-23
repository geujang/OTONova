<p align="center"><img src="assets/otonova-logo.png" width="128" alt="OTONova ロゴ"></p>

# OTONova V1.5

**Windows V1.5を公開しました。** プロジェクト保存・旧ラベルキャッシュの復元・既存OTO表示・WAV単位の自動原音設定・韓国語COC/CBNN/CMPX・Discordフォーラムへのフィードバックを追加しました。[V1.5変更履歴](RELEASE_NOTES.md)（韓国語）。macOS DMGはV1.0です。

[한국어](README.md) · [English](README.en.md) · **日本語** · [简体中文](README.zh-CN.md)

**UTAU音源向けのWindows・macOS用自動原音設定ツールです。** ファイル名・録音リスト・既存のoto.iniエイリアスから音素列を作成し、WFLモデルで強制アライメントを行い、所定のルールに従って原音設定値を生成します。

[Windowsインストーラー](https://github.com/geujang/OTONova/releases/tag/v1.5.0) · [対応形式・参考リスト](SUPPORTED_FORMATS.md) · [モデル容量の削減方法](MODEL_COMPRESSION.md) · [原作者クレジット](CREDITS.md) · [V1.0リリースノート](RELEASE_NOTES.md)

リンク先の技術資料は現在、韓国語で記載されています。

## macOS正式対応

Apple Silicon向けの[macOS版](https://github.com/geujang/OTONova/releases/tag/v1.0.0)を公開しています。Mac上でのアプリビルド、3言語モデルによるアライメント、GUI起動の検査を通過しています。Windows x64とmacOS Apple Siliconに正式対応しています。Windows版とMac版は同じV1.0リリースで配布しています。Intel Macには対応していません。実行方法と検証範囲は[MACOS.md](MACOS.md)をご覧ください。Apple Developer IDによる配布署名・公証は未実施です。

## 対応言語・音源形式

| 音源言語 | 対応形式 |
|---|---|
| 日本語 | CV（単独音）、CVVC、VCV（連続音） |
| 韓国語 | CV（単独音）、CVVC、CVC、VCV |
| 英語 | ARPAsing、CVVC（DELTA / Salem）、VCCV（PaintedCz CORE） |

ファイル名・録音リスト・既存エイリアスから録音方式を判別します。既存のoto.iniがある場合は、そのエイリアスを基準に設定値を生成します。

**中国語音源への対応は今後追加予定です。韓国語COC・CBNN・CMPXはCVVCの原音設定ルールを利用して開発ソースに追加しました。Windows V1.5インストーラーに収録しています。~~韓国語VCCV対応予定~~ — リスト未確認（元のリストが削除されたため）。** 現在、中国語はUI表示言語としてのみ提供しています。Android / iOSへの対応も今後追加予定で、現在の配布対象はWindows x64とmacOS Apple Siliconです。

## 主な機能

- WFLモデルによる音素境界推定と、ルールに基づくoto.ini生成。
- 第1段階で音素境界、第2段階で原音設定を編集。境界の変更時に原音設定を即時再計算。
- 波形・RMSエネルギー・最大15 kHzのスペクトログラム表示。カラーパレットは6種類。
- ラベル間を右クリックして、その区間だけを再生。第1段階では音素ラベル、第2段階では原音設定ラベルを使用。
- 原音設定ラベルのドラッグ、左から順に1～5キーで操作、Ctrl+Zで元に戻す。
- 韓国語・日本語・英語・中国語UI、ダーク／ライトモード、ユーザーごとの設定保存。
- Windowsインストール時にデスクトップショートカットの作成を選択可能。

## インストールと使い方

1. [Releases](https://github.com/geujang/OTONova/releases/tag/v1.0.0)から`OTONova-V1.0-Setup.exe`をダウンロードします。
2. 空の新規フォルダーにインストールします。Pythonとモデルが同梱されているため、別途インストールは不要です。デスクトップショートカットの作成も選択できます。
3. `OTONova.exe`を起動し、音源フォルダー・言語・録音形式を選び、音素境界推定／原音設定生成を実行します。
4. **第1段階**で音素境界を確認し、**第2段階**で原音設定値を調整します。
5. 音素境界の編集は境界キャッシュに保存され、第2段階の編集はoto.iniに反映されます。編集セッションの初回保存時に既存のoto.iniをバックアップします。

英語VCCVでは、COREのサブフォルダー内にあるWAVとoto.iniを認識します。既存のotoがない場合のみエイリアスを自動生成し、重複を除去します。自動推定後は試聴と境界の確認をおすすめします。初回解析はモデルの読み込みと解析コードの初期化に時間がかかる場合があります。

## モデル容量の削減方法

学習状態の除去、同一Whisperエンコーダーの共有、チェックポイントの可逆圧縮を行いました。**量子化・FP16変換・音素の削除は行わず、FP32推論重みを保持しています。** モデル関連ファイルの合計は約1.35 GBから、共有化後に約304 MB、可逆圧縮後に約254 MBになりました。ランタイムを含むWindows版のインストール後のファイル合計は約804 MBです。ディスク上の使用量はファイルシステムの割り当て単位によって異なります。詳細と検証範囲は[MODEL_COMPRESSION.md](MODEL_COMPRESSION.md)をご覧ください。

## ソースからの実行・ビルド

[DEVELOPMENT.md](DEVELOPMENT.md)をご覧ください。このリポジトリにはコード・設定・音素表・録音リスト識別カタログを収録し、モデル重みとランタイムはReleasesのインストーラーで提供します。ユーザー音源・学習データ・個人PCのパス・過去の大きなモデルを含む開発用Git履歴は公開リポジトリに含めていません。

## クレジット

- WFL原作者：[MLo7Ghinsan / Ghin_MLo7 — WFL-ASR](https://github.com/MLo7Ghinsan/WFL-ASR)、MIT。
- 英語モデル：[Superbox2147](https://github.com/Superbox2147)。
- 日本語・韓国語モデル：[Archivoice](https://github.com/Archivoice)。
- 共通エンコーダー：[OpenAI Whisper base](https://huggingface.co/openai/whisper-base)。
- 学習データセット・録音リスト制作者・音素対応表・原文の利用条件：[CREDITS.md](CREDITS.md)、[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

制作：**KURO / geujang**。不具合は、使用言語・形式・再現手順・エラー内容を添えて[Issues](https://github.com/geujang/OTONova/issues)へお寄せください。
