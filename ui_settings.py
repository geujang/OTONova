"""User-facing translations and persistent OtoNova appearance preferences."""
import weakref
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QLabel, QPushButton

LANGUAGES = {'ko': '한국어', 'ja': '日本語', 'en': 'English', 'zh': '简体中文'}
language = 'ko'
theme = 'dark'
spectrum_palette = 'classic'
_sources = {}
# Source Korean, Japanese, English, simplified Chinese. Never applied to audio data.
_ROWS = """
작업|操作|Actions|操作
설정|設定|Settings|设置
표시 언어|表示言語|Display language|显示语言
화면 모드|表示モード|Appearance|外观
다크|ダーク|Dark|深色
라이트|ライト|Light|浅色
크레딧|クレジット|Credits|致谢
모델 크레딧|モデルのクレジット|Model credits|模型致谢
확인|OK|OK|确定
취소|キャンセル|Cancel|取消
닫기|閉じる|Close|关闭
음원 폴더|音源フォルダー|Voicebank folder|音源文件夹
형식: |形式: |Format: |格式：
연속음|連続音|VCV|连续音
일본어|日本語|Japanese|日语
한국어|韓国語|Korean|韩语
한국어 COC|韓国語 COC|Korean COC|韩语 COC
한국어 CBNN|韓国語 CBNN|Korean CBNN|韩语 CBNN
한국어 CMPX|韓国語 CMPX|Korean CMPX|韩语 CMPX
영어|英語|English|英语
자동 원설기|自動原音設定ツール|Automatic oto editor|自动原音设定工具
자동 원설|自動原音設定|Automatic oto configuration|自动原音设定
파일명 / 인덱스 인식 → 모델 음소 정렬 → 지정 규칙으로 원설 생성|ファイル名 / インデックス認識 → 音素アラインメント → 原音設定|Filename / index recognition → phoneme alignment → oto generation|文件名 / 索引识别 → 音素对齐 → 原音设定
VCV 원설 생성|VCV 原音設定を生成|Generate VCV oto|生成 VCV 原音设定
음소 경계 추정 / 원설 생성|音素境界推定 / 原音設定生成|Align phonemes / generate oto|音素边界推断 / 生成原音设定
중지|停止|Stop|停止
oto.ini 저장 (기존 파일 백업)|oto.ini を保存（既存ファイルをバックアップ）|Save oto.ini (back up existing file)|保存 oto.ini（备份现有文件）
준비|準備完了|Ready|就绪
1단계 · 음소 경계|ステップ 1 · 音素境界|Step 1 · Phoneme boundaries|第 1 步 · 音素边界
2단계 · 원설 조정|ステップ 2 · 原音設定|Step 2 · Oto adjustment|第 2 步 · 原音设定调整
선택한 WAV 듣기|選択した WAV を再生|Play selected WAV|播放所选 WAV
검토 항목만 보기|要確認項目のみ表示|Show warnings only|仅显示待检查项
확대 +|拡大 +|Zoom in +|放大 +
축소 -|縮小 -|Zoom out -|缩小 -
전체 보기|全体表示|Fit view|显示全部
경계 되돌리기 (Ctrl+Z)|変更を元に戻す (Ctrl+Z)|Undo edit (Ctrl+Z)|撤销修改 (Ctrl+Z)
파일 · 현재 단계의 경고|ファイル · 現在のステップの警告|Files · Current step warnings|文件 · 当前步骤警告
에일리어스|エイリアス|Alias|别名
오프셋|オフセット|Offset|偏移
오버랩|オーバーラップ|Overlap|重叠
선행|先行発声|Preutterance|预先发声
고정 끝|固定範囲の終点|Fixed end|固定区间终点
고정|固定範囲|Fixed|固定区间
컷오프|カットオフ|Cutoff|截止
검토|要確認|Review|检查
언어권|言語|Language|语言
형식|形式|Format|格式
언어권을 선택하세요|言語を選択してください|Select a language|请选择语言
언어권을 먼저 선택하세요|先に言語を選択してください|Select a language first|请先选择语言
형식을 선택하세요|形式を選択してください|Select a format|请选择格式
음원 형식 선택|音源形式の選択|Select voicebank format|选择音源格式
언어와 녹음 리스트 형식을 선택하세요.|言語と録音リスト形式を選択してください。|Choose the language and recording format.|请选择语言和录音列表格式。
세부 녹음 방식은 파일명·녹음 리스트·기존 에일리어스로 자동 인식합니다.|ファイル名・録音リスト・既存エイリアスから詳細形式を自動認識します。|Recording variants are detected from filenames, reclists and existing aliases.|根据文件名、录音列表及现有别名自动识别具体格式。
기존 oto.ini가 있으면 그 에일리어스 목록을 유지합니다.|既存 oto.ini のエイリアスを維持します。|Existing oto.ini aliases are preserved.|保留现有 oto.ini 的别名。
음소 경계만 드래그하여 수정합니다. 원설 라벨은 2단계에서 표시됩니다.|音素境界をドラッグして修正します。原音設定はステップ 2 で表示します。|Drag phoneme boundaries to edit. Oto markers appear in step 2.|拖动音素边界进行修改。原音设定标记在第 2 步显示。
음소 경계는 잠깁니다. 원설 선을 드래그하거나 파형 위에서 왼쪽부터 1~5 키를 눌러 커서 위치로 이동하세요. 키를 누른 채 이동할 수도 있습니다.|音素境界はロックされます。原音設定の線をドラッグするか、波形上で左から 1～5 キーを押してカーソル位置へ移動します。|Phoneme boundaries are locked. Drag oto markers, or use keys 1–5 (left to right) to move them to the cursor. Hold a key to follow the cursor.|音素边界已锁定。拖动原音设定线，或按从左到右的 1–5 键移至光标位置。按住按键可跟随光标。
원설 행 선택 → 음소 경계 드래그 → 즉시 재계산|原音設定を選択 → 音素境界をドラッグ → 即時再計算|Select an oto entry → drag a phoneme boundary → instant recalculation|选择原音设定 → 拖动音素边界 → 即时重新计算
파형|波形|Waveform|波形
스펙토그램|スペクトログラム|Spectrogram|频谱图
음원 없음|音源なし|No audio|无音频
선택한 폴더에 WAV가 없습니다.|選択したフォルダーに WAV がありません。|No WAV files in the selected folder.|所选文件夹中没有 WAV 文件。
음소 경계 저장 완료|音素境界を保存しました|Phoneme boundaries saved|音素边界已保存
수정 경계와 oto.ini 저장 완료|境界と oto.ini を保存しました|Boundaries and oto.ini saved|边界和 oto.ini 已保存
수정 저장 실패: |変更の保存に失敗: |Failed to save edits: |保存修改失败：
저장 완료: |保存完了: |Saved: |已保存：
추정된 음소 경계 없음|推定された音素境界なし|No estimated phoneme boundaries|没有推断的音素边界
음소 경계 파일을 읽을 수 없음|音素境界ファイルを読み込めません|Cannot read phoneme boundaries|无法读取音素边界文件
음소 경계 없음|音素境界なし|No phoneme boundaries|没有音素边界
음소 구간 길이가 0 이하|音素の長さが 0 以下|Non-positive phoneme duration|音素区间长度不大于零
15ms 미만 음소: 경계 확인 필요|15ms 未満の音素: 境界を確認|Phoneme shorter than 15ms: check boundary|音素短于 15ms：请检查边界
음소 경계 사이에 빈 구간 또는 겹침|音素境界に空白または重複|Gap or overlap between phonemes|音素边界之间存在间隙或重叠
원설 생성 불가: |原音設定を生成できません: |Cannot generate oto: |无法生成原音设定：
리스트 일치|リスト一致|Reclist match|列表匹配
미등록|未登録|Unrecognized|未识别
일치하는 공식 리스트 항목 없음|公式リストに一致なし|No matching official reclist entry|没有匹配的官方列表条目
현재 WAV 분석이 끝나면 중지됩니다. 그 후 창을 닫아주세요.|現在の WAV の解析後に停止します。その後ウィンドウを閉じてください。|Stopping after the current WAV finishes. Close the window afterwards.|当前 WAV 分析完成后停止，之后即可关闭窗口。
해당 WAV의 경계가 없어 기존 원설 값을 유지합니다.|境界がないため既存の原音設定を維持します。|No boundaries for this WAV; existing oto values are retained.|该 WAV 没有边界，保留现有原音设定。
개 원설|件の原音設定| oto entries| 个原音设定
중복 |重複 |Duplicates |重复 
개 제거|件を除去| removed| 个已移除
실패 |失敗 |Failures |失败 
"""
_ROWS += """
보라색 점선 음소 경계를 드래그하세요 · 즉시 재계산 · 놓으면 경계와 oto.ini 자동 저장|紫の点線をドラッグ · 即時再計算 · 離すと自動保存|Drag purple phoneme boundaries · instant recalculation · release to save|拖动紫色虚线边界 · 即时重新计算 · 松开自动保存
음소 처리 규칙이 변경되었습니다. 생성을 눌러 다시 추정해주세요.|音素処理規則が変更されました。再生成してください。|Phoneme rules changed. Generate again to realign.|音素处理规则已更改，请重新生成。
영어 음소 매핑이 변경되었습니다. 다시 생성해주세요.|英語音素の対応が変更されました。再生成してください。|English phoneme mapping changed. Generate again.|英语音素映射已更改，请重新生成。
형식의 음소열이 변경되었습니다. 생성을 눌러 다시 추정해주세요.|音素列が変更されました。再生成してください。|The format phoneme sequence changed. Generate again.|格式的音素序列已更改，请重新生成。
원설 생성을 눌러주세요|原音設定を生成してください|Press Generate oto|请点击生成原音设定
드래그 즉시 재계산 / 놓으면 자동 저장|ドラッグで再計算 / 離すと保存|Drag to recalculate / release to save|拖动即时计算 / 松开自动保存
녹음 리스트 자동 인식 완료|録音リストの認識完了|Reclist detection complete|录音列表识别完成
한숨을 SP로 정렬한 경계: 확인 필요|息を SP として整列: 要確認|Breath aligned as SP: check boundary|呼吸音按 SP 对齐：请检查
음소 경계선 드래그: 실시간 원설 · 휠: 확대/축소 · 아래 스크롤바: 이동|音素境界をドラッグ: 即時設定 · ホイール: 拡大縮小 · 下のバー: 移動|Drag boundaries: live oto · Wheel: zoom · Bottom scrollbar: pan|拖动边界：实时原音设定 · 滚轮：缩放 · 底部滚动条：移动
"""
_ROWS += """
공식 리스트 일치|公式リスト一致|official reclist match|匹配官方列表
개 공식 리스트 일치|件の公式リスト一致| official reclist match(es)| 个官方列表匹配
"""
_ROWS += """
WAV 범위 또는 짧은 구간 때문에 규칙값을 보정함|WAV の範囲または短い区間に合わせて補正|Rule values adjusted for WAV bounds or short segments|因 WAV 范围或区间过短而调整规则值
고정 끝이 선행보다 앞: 청음 검토 필요|固定範囲の終点が先行発声より前: 要試聴|Fixed end precedes preutterance: listen to check|固定区间终点早于预先发声：请试听检查
컷오프가 오프셋보다 앞이거나 같음|カットオフがオフセット以前|Cutoff is at or before offset|截止位置不晚于偏移
고정 끝이 사용 구간 밖에 있음|固定範囲の終点が使用区間外|Fixed end is outside the usable range|固定区间终点超出使用区间
선행이 사용 구간 밖에 있음|先行発声が使用区間外|Preutterance is outside the usable range|预先发声超出使用区间
오버랩이 선행보다 뒤에 있음|オーバーラップが先行発声より後|Overlap is after preutterance|重叠晚于预先发声
기존 에일리어스 대응 경계를 찾지 못해 원래 시간값 유지|対応する境界がないため既存の時間値を維持|No matching alias boundary; original timing retained|未找到别名对应边界，保留原有时间值
에일리어스 대응 불가: 기존 시간 위치를 경계에 연동하여 수정|エイリアス対応なし: 既存の時間位置を境界に連動|No alias match: existing timing follows boundary edits|无法匹配别名：现有时间位置随边界调整
"""
_ROWS += """
에너지|エネルギー|Energy|能量
스펙트로그램 색상|スペクトログラムの配色|Spectrogram colors|频谱图配色
기본|標準|Classic|默认
보라 · 분홍|紫 · ピンク|Purple · Pink|紫色 · 粉色
불꽃|炎|Fire|火焰
바다|海|Ocean|海洋
무지개|虹|Rainbow|彩虹
흑백|白黒|Grayscale|黑白
우클릭: 라벨 사이 구간 재생|右クリック: ラベル間を再生|Right-click: play between labels|右键：播放标签之间的区间
"""

_ROWS += """
도움말|ヘルプ|Help|帮助
업데이트 확인|更新を確認|Check for updates|检查更新
GitHub 링크|GitHubを開く|GitHub link|GitHub 链接
버전 정보|バージョン情報|About|版本信息
피드백 (준비 중)|フィードバック（準備中）|Feedback (coming soon)|反馈（准备中）
외부 파일 변경|外部ファイルの変更|External file changes|外部文件更改
WAV 파일을 재로드 하고 시각음성자료를 다시 재 렌더링 할까요?|WAVを再読み込みして波形・エネルギー・スペクトログラムを再描画しますか？|Reload WAV files and render waveform, energy and spectrogram data again?|重新加载 WAV 并重新渲染波形、能量和声谱图吗？
OTO 파일을 재 인식 할까요?|OTOファイルを再読み込みしますか？|Read the OTO files again?|重新识别 OTO 文件吗？
다시 로드|再読み込み|Reload|重新加载
재인식|再認識|Read again|重新识别
새 버전이 있습니다. 다운로드 페이지를 열까요?|新しいバージョンがあります。ダウンロードページを開きますか？|A new version is available. Open the download page?|有新版本可用。打开下载页面吗？
현재 버전은 V1.5입니다. 더 새로운 공개 릴리스가 없습니다.|現在のバージョンはV1.5です。より新しい公開リリースはありません。|Current version: V1.5. No newer public release is available.|当前版本为 V1.5，暂无更新的公开版本。
업데이트 정보를 확인할 수 없습니다.|更新情報を確認できません。|Could not check for updates.|无法检查更新信息。
"""


_ROWS += """
피드백|フィードバック|Feedback|反馈
오류 제보|不具合報告|Report a bug|报告错误
기능 제안|機能提案|Suggest a feature|功能建议
기타|その他|Other|其他
답변 받을 연락처 (선택)|返信先（任意）|Contact for replies (optional)|回复联系方式（可选）
피드백 내용 (최대 1,500자)|内容（最大1,500文字）|Feedback (up to 1,500 characters)|反馈内容（最多 1,500 字符）
전송|送信|Send|发送
전송 중…|送信中…|Sending…|正在发送…
작성 내용·선택한 연락처·분류·앱 버전을 Discord 피드백 포럼에 게시합니다. 채널을 볼 수 있는 서버 멤버에게 공개됩니다. 음원·OTO·로그는 전송하지 않습니다.|入力内容・任意の連絡先・分類・バージョンをDiscordのフィードバックフォーラムに投稿します。チャンネルを閲覧できるサーバーメンバーに公開されます。音源・OTO・ログは送信しません。|Your message, optional contact, category and app version are posted to the Discord feedback forum, visible to server members with channel access. Audio, OTO and logs are not sent.|内容、可选联系方式、分类及版本将发布至 Discord 反馈论坛，拥有频道访问权限的服务器成员可见。不发送音频、OTO 或日志。
피드백 서버 연결 준비 중입니다. 작성한 내용은 이 PC에 보관됩니다.|フィードバックサーバーは準備中です。下書きはこのPCに保存します。|The feedback server is not connected yet. Your draft is saved on this PC.|反馈服务器尚未连接，草稿保存在本机。
Discord 피드백 포럼에 게시했습니다.|Discordのフィードバックフォーラムに投稿しました。|Posted to the Discord feedback forum.|已发布至 Discord 反馈论坛。
전송이 제한되었습니다. 잠시 후 다시 보내주세요.|送信制限に達しました。しばらくしてから再送信してください。|Sending is temporarily limited. Please try again later.|发送暂时受限，请稍后重试。
전송하지 못했습니다. 내용은 보관되어 있으니 다시 시도해주세요.|送信できませんでした。下書きは保存されています。再試行してください。|Could not send. Your draft is saved; please try again.|发送失败，草稿已保存，请重试。
내용은 1~1,500자까지 입력해주세요.|内容は1～1,500文字で入力してください。|Enter between 1 and 1,500 characters.|请输入 1 至 1,500 个字符。
연락처는 100자 이하로 입력해주세요.|連絡先は100文字以内で入力してください。|Keep contact details within 100 characters.|联系方式请勿超过 100 个字符。
"""

TRANSLATIONS = {r.split('|')[0]: r.split('|')[1:] for r in _ROWS.strip().splitlines() if r.strip()}

def translate(text):
    text = str(text)
    if language == 'ko': return text
    column = {'ja':0, 'en':1, 'zh':2}[language]
    if text in TRANSLATIONS: return TRANSLATIONS[text][column]
    # Only UI prose reaches this function; audio aliases and paths stay untouched.
    for source in sorted(TRANSLATIONS, key=len, reverse=True):
        if len(source) >= 2: text = text.replace(source, TRANSLATIONS[source][column])
    return text

def _remember(widget, method, source):
    key=id(widget)
    _sources[key]=(weakref.ref(widget, lambda ref: _sources.pop(key,None)),method,source)

def append_log(widget, source):
    existing=getattr(widget,'_ui_log_source',[])
    existing.append(str(source))
    widget._ui_log_source=existing
    _remember(widget,'setPlainText','\n'.join(existing))
    widget.appendPlainText(translate(source))

def set_text(widget, source):
    _remember(widget, 'setText', source)
    widget.setText(translate(source))

def set_title(widget, source):
    _remember(widget, 'setWindowTitle', source)
    widget.setWindowTitle(translate(source))

def label(source='', *args):
    widget = QLabel(*args); set_text(widget, source); return widget

def button(source='', *args):
    widget = QPushButton(*args); set_text(widget, source); return widget

def refresh():
    for ref, method, source in list(_sources.values()):
        widget=ref()
        if widget is None:continue
        try: getattr(widget, method)(translate(source))
        except RuntimeError: pass  # Dialog already destroyed by Qt.

def colors():
    if theme == 'light':
        return dict(bg='#faf6ff',panel='#ffffff',raised='#eee2fa',text='#32194c',muted='#715a85',border='#d7bde9',accent='#8030bd',hover='#e2c9fa',warning='#935200',wave='#8545bc')
    return dict(bg='#191126',panel='#231832',raised='#342046',text='#f4eafa',muted='#bd9dce',border='#56316d',accent='#a05aeb',hover='#623584',warning='#ffd180',wave='#d29afd')

def stylesheet():
    c=colors()
    return f"""QWidget {{background:{c['bg']}; color:{c['text']}; font-size:13px;}}
    QPushButton {{background:{c['raised']}; border:1px solid {c['border']}; padding:8px 12px; border-radius:6px;}}
    QPushButton:hover {{background:{c['hover']}; border-color:#c17df0;}}
    QPushButton:checked {{background:{c['accent']}; color:white; border-color:#ec99ea;}}
    QPushButton:disabled {{color:{c['muted']};}}
    QLineEdit,QPlainTextEdit,QTextBrowser,QTableWidget,QListWidget,QComboBox {{background:{c['panel']};border:1px solid {c['border']};padding:4px;selection-background-color:{c['accent']};selection-color:white;}}
    QHeaderView::section {{background:{c['raised']};padding:7px;border:0;}}
    QProgressBar {{border:1px solid {c['border']};border-radius:4px;text-align:center;}}
    QProgressBar::chunk {{background:{c['accent']};}}
    QScrollBar {{background:{c['panel']};}} QScrollBar::handle {{background:{c['border']}; min-width:18px;min-height:18px;border-radius:4px;}}
    QToolTip {{background:{c['raised']};color:{c['text']};border:1px solid {c['border']};}}
    """

_font_ids = {}
def apply_font():
    from pathlib import Path
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication
    import sys
    if sys.platform=='darwin':
        families={'ko':['Apple SD Gothic Neo'], 'ja':['Hiragino Sans'], 'en':['Helvetica Neue'], 'zh':['PingFang SC']}
        font=QFont();font.setFamilies(families[language]+['Arial Unicode MS','sans-serif']);font.setPointSize(10)
        app=QApplication.instance()
        if app:app.setFont(font)
        return
    fonts={'ko':('malgun.ttf','Malgun Gothic'), 'ja':('meiryo.ttc','Meiryo'),
           'en':('malgun.ttf','Malgun Gothic'), 'zh':('msyh.ttc','Microsoft YaHei UI')}
    filename,family=fonts[language]
    path=Path('C:/Windows/Fonts')/filename
    if filename not in _font_ids and path.exists():_font_ids[filename]=QFontDatabase.addApplicationFont(str(path))
    font=QFont(family,10)
    if filename in _font_ids:
        families=QFontDatabase.applicationFontFamilies(_font_ids[filename])
        if families:font.setFamilies([family]+families+['Segoe UI'])
    app=QApplication.instance()
    if app:app.setFont(font)
