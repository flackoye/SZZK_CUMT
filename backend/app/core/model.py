"""V3-Full (FullModelStandard) PyTorch model architecture definition."""
from __future__ import annotations

import torch
from torch import nn


class FullModelStandard(nn.Module):
    """Standard V3 dual-branch fusion network (CNN-BiLSTM sequence branch + multi-scale physics MLP branch)."""

    def __init__(
        self,
        seq_channels: int = 3,
        phys_dim: int = 80,
        cnn_channels: int = 64,
        lstm_hidden: int = 40,
        fusion_hidden: int = 128,
        dropout: float = 0.25,
    ):
        super().__init__()
        self.seq_cnn = nn.Sequential(
            nn.Conv1d(seq_channels, 32, kernel_size=5, padding=2),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.Conv1d(32, cnn_channels, kernel_size=5, padding=2),
            nn.BatchNorm1d(cnn_channels),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Dropout(dropout),
        )
        self.seq_lstm = nn.LSTM(
            cnn_channels, lstm_hidden, num_layers=1, batch_first=True, bidirectional=True
        )
        self.phys_branch = nn.Sequential(
            nn.Linear(phys_dim, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(),
        )
        self.fusion_fc = nn.Sequential(
            nn.Linear(lstm_hidden * 2 + 64, fusion_hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(fusion_hidden, fusion_hidden // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
        )
        self.damage_head = nn.Linear(fusion_hidden // 2, 5)
        self.stress_head = nn.Linear(fusion_hidden // 2, 5)
        self.state_head = nn.Linear(fusion_hidden // 2, 25)

    def forward(self, seq: torch.Tensor, phys: torch.Tensor) -> dict[str, torch.Tensor]:
        # seq shape: (batch_size, seq_len=100, channels=3)
        # Transpose for Conv1d: (batch_size, channels=3, seq_len=100)
        z = self.seq_cnn(seq.transpose(1, 2)).transpose(1, 2)
        out, _ = self.seq_lstm(z)
        seq_feat = torch.mean(out, dim=1)
        phys_feat = self.phys_branch(phys)
        fused = self.fusion_fc(torch.cat([seq_feat, phys_feat], dim=1))
        return {
            "damage": self.damage_head(fused),
            "stress": self.stress_head(fused),
            "state": self.state_head(fused),
        }

