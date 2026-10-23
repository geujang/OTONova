"""Voicebank formats; model language and alias conventions are independent."""
FORMATS = {
    'ja_cv': ('일본어 단독음 (CV)', 'ja', 'cv'),
    'vcv': ('일본어 연속음 (VCV)', 'ja', 'vcv'),
    'cvvc': ('일본어 CVVC', 'ja', 'cvvc'),
    'vcv_cvvc': ('일본어 VCV & CVVC', 'ja', 'vcv_cvvc'),
    'ko_cv': ('한국어 단독음 (CV)', 'ko', 'cv'),
    'ko_cvvc_malcha': ('한국어 CVVC · 말차식 9모라', 'ko', 'cvvc'),
    'ko_cvvc_tabi': ('한국어 CVVC · 마따따비식 신버전', 'ko', 'cvvc'),
    'ko_cvvc_tabi_old': ('한국어 CVVC · 마따따비식 구버전', 'ko', 'cvvc'),
    'ko_cvc_zetty': ('한국어 CVC · 제티식', 'ko', 'cvc'),
    'ko_cvc_binbin': ('한국어 CVC · 빈빈식', 'ko', 'cvc'),
    'ko_cvc_gyutaeng': ('한국어 CVC · 규탱식 Light', 'ko', 'cvc'),
    'ko_cvc_gyutaeng_plus': ('한국어 CVC · 규탱식 Plus', 'ko', 'cvc'),
    'ko_vcv_diko': ('한국어 VCV · 서딕호식 기본', 'ko', 'vcv'),
    'ko_vcv_diko_ex': ('한국어 VCV · 서딕호식 특수음소 포함', 'ko', 'vcv'),
    'ko_vcv_malcha7': ('한국어 VCV · 말차식 7모라', 'ko', 'vcv'),
    'ko_vcv_malcha15': ('한국어 VCV · 말차식 15모라', 'ko', 'vcv'),
    'ko_cvvc': ('한국어 CVVC · 기존 파일명 방식', 'ko', 'legacy'),
}

def is_korean(mode):
    return FORMATS[mode][1] == 'ko'

# Public choices describe the recording structure; named profiles remain internal.
PUBLIC_FORMATS = {
    'ko_coc': ('한국어 COC', 'ko', 'coc'),
    'ko_cbnn': ('한국어 CBNN', 'ko', 'cbnn'),
    'ko_cmpx': ('한국어 CMPX', 'ko', 'cmpx'),
    'ko_auto_cvvc': ('한국어 CVVC', 'ko', 'cvvc'),
    'ko_auto_cvc': ('한국어 CVC', 'ko', 'cvc'),
    'ko_auto_vcv': ('한국어 VCV', 'ko', 'vcv'),
    'ko_cv': ('한국어 CV', 'ko', 'cv'),
    'cvvc': ('일본어 CVVC', 'ja', 'cvvc'),
    'ja_cv': ('일본어 CV', 'ja', 'cv'),
    'vcv': ('일본어 VCV', 'ja', 'vcv'),
    'en_arpasing': ('영어 ARPAsing', 'en', 'arpasing'),
    'en_cvvc': ('영어 CVVC', 'en', 'cvvc'),
    'en_vccv': ('영어 VCCV', 'en', 'vccv'),
}
FORMATS.update(PUBLIC_FORMATS)
for _key, (_label, _language, _kind) in list(FORMATS.items()):
    if _language == 'ko':FORMATS[_key] = ('한국어 '+_kind.upper() if _kind!='legacy' else '한국어 CVVC', _language, _kind)

def public_mode(mode):
    if mode in PUBLIC_FORMATS:return mode
    language,kind=FORMATS[mode][1:]
    if language=='ko':return 'ko_auto_'+('cvvc' if kind=='legacy' else kind)
    return 'vcv' if mode=='vcv_cvvc' else mode
