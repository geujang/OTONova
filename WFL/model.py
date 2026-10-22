import os
import torch
import torch.nn as nn
import torchaudio
from transformers import WhisperFeatureExtractor, WhisperModel

class FocalLoss(nn.Module):
    def __init__(self, alpha=0.25, gamma=2.0, ignore_index=-100):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.ignore_index = ignore_index
        self.ce = nn.CrossEntropyLoss(ignore_index=ignore_index, reduction='none')

    def forward(self, logits, targets):
        logits = logits.float()
        log_pt = -self.ce(logits, targets)
        pt = torch.exp(log_pt)
        pt = torch.clamp(pt, min=1e-8, max=1.0 - 1e-8)
        loss = self.alpha * (1 - pt) ** self.gamma * self.ce(logits, targets)
        return loss.mean()

class SpecAugment(nn.Module):
    def __init__(self, freq_mask_param=20, time_mask_param=30):
        super().__init__()
        self.freq_mask = torchaudio.transforms.FrequencyMasking(freq_mask_param)
        self.time_mask = torchaudio.transforms.TimeMasking(time_mask_param)

    def forward(self, x):
        x = x.transpose(1, 2)
        x = self.freq_mask(x)
        x = self.time_mask(x)
        return x.transpose(1, 2)

class FeedForwardModule(nn.Module):
    def __init__(self, dim, expansion=4, dropout=0.1):
        super().__init__()
        self.net = nn.Sequential(
            nn.LayerNorm(dim),
            nn.Linear(dim, dim * expansion),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(dim * expansion, dim),
            nn.Dropout(dropout),
        )

    def forward(self, x):
        return self.net(x)

class ConformerBlock(nn.Module):
    def __init__(self, dim, heads=4, ff_expansion=4, conv_kernel=31, dropout=0.1):
        super().__init__()
        self.ff1 = FeedForwardModule(dim, ff_expansion, dropout)
        self.ff2 = FeedForwardModule(dim, ff_expansion, dropout)
        self.self_attn = nn.MultiheadAttention(embed_dim=dim, num_heads=heads, dropout=dropout, batch_first=True)
        self.ln1 = nn.LayerNorm(dim)
        self.ln2 = nn.LayerNorm(dim)
        self.conv = nn.Sequential(
            nn.Conv1d(dim, 2 * dim, kernel_size=1),
            nn.GLU(dim=1),
            nn.Conv1d(dim, dim, kernel_size=conv_kernel, padding=conv_kernel // 2),
            nn.BatchNorm1d(dim),
            nn.GELU(),
            nn.Conv1d(dim, dim, kernel_size=1),
            nn.Dropout(dropout)
        )

    def forward(self, x):
        x = x + 0.5 * self.ff1(x)
        attn_out, _ = self.self_attn(x, x, x)
        x = self.ln1(x + attn_out)
        x_ln = self.ln2(x)
        x_conv = self.conv(x_ln.transpose(1, 2)).transpose(1, 2)
        if x.size(1) != x_conv.size(1): 
             x_conv = x_conv[:, :x.size(1)]
        x = x + x_conv
        x = x + 0.5 * self.ff2(x)
        return x

class BIOPhonemeTagger(nn.Module):
    def __init__(self, config, label_list):
        super().__init__()
        self.config = config
        self.encoder_type = config["model"].get("encoder_type", "whisper").lower()
        model_name = config["model"].get("whisper_model", "openai/whisper-base")

        encoder_dir = os.path.join(os.getcwd(), "encoder")

        if self.encoder_type == "whisper":
            if not os.path.exists(encoder_dir) or not os.listdir(encoder_dir):
                print(f"Downloading Whisper ({model_name}) to local directory: {encoder_dir} ...")
                os.makedirs(encoder_dir, exist_ok=True)
                ext = WhisperFeatureExtractor.from_pretrained(model_name)
                mod = WhisperModel.from_pretrained(model_name)
                ext.save_pretrained(encoder_dir)
                mod.save_pretrained(encoder_dir)
                del mod 
            
            self.feature_extractor = WhisperFeatureExtractor.from_pretrained(encoder_dir)
            self.encoder = WhisperModel.from_pretrained(encoder_dir).encoder
            hidden_size = self.encoder.config.d_model
        else:
            self.encoder = None
            self.feature_extractor = None
            self.mel_extractor = torchaudio.transforms.MelSpectrogram(
                sample_rate=config["data"]["sample_rate"], n_fft=400,
                hop_length=int(config["data"].get("frame_duration", 0.02) * config["data"]["sample_rate"]),
                n_mels=config["data"].get("n_mels", 80)
            )
            hidden_size = self.mel_extractor.n_mels

        self.lang_emb_dim = config["model"].get("lang_emb_dim", 64)
        self.lang_emb = nn.Embedding(config["model"]["num_languages"], self.lang_emb_dim)
        self.lang_proj = nn.Linear(hidden_size + self.lang_emb_dim, hidden_size)

        if self.encoder:
            if config["model"].get("freeze_encoder", False):
                for param in self.encoder.parameters():
                    param.requires_grad = False
                
                unfreeze_n = config["model"].get("unfreeze_last_n_layers", 0)
                if unfreeze_n > 0:
                    if hasattr(self.encoder, "layers"): 
                        for layer in self.encoder.layers[-unfreeze_n:]:
                            for param in layer.parameters():
                                param.requires_grad = True

        self.spec_aug = SpecAugment()
        
        self.conformer_layers = nn.ModuleList([
            ConformerBlock(
                dim=hidden_size,
                heads=config["model"].get("conformer_heads", 4),
                ff_expansion=config["model"].get("conformer_ff_expansion", 4),
                conv_kernel=config["model"].get("conformer_kernel_size", 31),
                dropout=config["model"].get("conformer_dropout", 0.1)
            )
            for _ in range(config["model"].get("num_conformer_layers", 2))
        ])

        if config["model"].get("enable_dilated_conv", True):
            convs = []
            depth = config["model"].get("dilated_conv_depth", 2)
            k_size = config["model"].get("dilated_conv_kernel", 3)
            for i in range(depth):
                dilation = 2 ** i
                padding = dilation * (k_size - 1) // 2
                convs.append(nn.Conv1d(hidden_size, hidden_size, kernel_size=k_size, dilation=dilation, padding=padding))
                convs.append(nn.GELU())
            self.dilated_conv_stack = nn.Sequential(*convs)
        else:
            self.dilated_conv_stack = nn.Identity()

        self.classifier = nn.Linear(hidden_size, len(label_list))
        self.boundary_offset_head = nn.Sequential(
            nn.Conv1d(hidden_size, hidden_size, kernel_size=3, padding=1),
            nn.GELU(),
            nn.Conv1d(hidden_size, 2, kernel_size=1),
            nn.Sigmoid()
        )

        self.envelope_dim = config["model"].get("envelope_dim", 20)
        self.envelope_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.GELU(),
            nn.Linear(hidden_size // 2, self.envelope_dim)
        )

        self.label_list = label_list
        self.label2id = {label: i for i, label in enumerate(label_list)}
        self.id2label = {i: label for label, i in self.label2id.items()}

    def forward(self, input_values, lang_id=None, max_label_len=None):
        if self.encoder_type == "whisper":
            features = self.feature_extractor(input_values.cpu().numpy(), sampling_rate=16000, return_tensors="pt")
            input_features = features["input_features"].to(input_values.device)
            hidden_states = self.encoder(input_features).last_hidden_state
        else:
            hidden_states = self.mel_extractor(input_values).transpose(1, 2)

        if self.training:
            hidden_states = self.spec_aug(hidden_states)

        if max_label_len is not None:
            if hidden_states.size(1) > max_label_len:
                hidden_states = hidden_states[:, :max_label_len, :]
            elif hidden_states.size(1) < max_label_len:
                pad = torch.zeros(hidden_states.size(0), max_label_len - hidden_states.size(1), hidden_states.size(2), device=hidden_states.device)
                hidden_states = torch.cat([hidden_states, pad], dim=1)

        if lang_id is not None:
            lang_embed = self.lang_emb(lang_id).unsqueeze(1).expand(-1, hidden_states.size(1), -1)
            hidden_states = self.lang_proj(torch.cat([hidden_states, lang_embed], dim=-1))

        out = hidden_states
        for layer in self.conformer_layers:
            out = layer(out)

        out = self.dilated_conv_stack(out.transpose(1, 2)).transpose(1, 2)

        logits = self.classifier(out)
        offsets = self.boundary_offset_head(out.transpose(1, 2)).transpose(1, 2)
        
        pred_envelope = self.envelope_head(out)
        
        return logits, offsets, pred_envelope