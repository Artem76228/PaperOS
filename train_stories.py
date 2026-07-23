import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "datasets", "torch"], check=False)

# ── Config — MUST match myai_engine.h ───────────────────────────────
VOCAB_SIZE   = 256
N_EMBD       = 192
N_LAYER      = 12
N_HEAD       = 6
HEAD_DIM     = N_EMBD // N_HEAD
CTX_LEN      = 256
FF_DIM       = 4 * N_EMBD
N_TENSORS    = 2 + N_LAYER * 10 + 3   # 125

BATCH_SIZE   = 96
LR           = 3e-4
WARMUP_STEPS = 400
EPOCHS       = 20
CKPT         = "model_stories.pt"
OUT_BIN      = "model.bin"

SAVE_TO_DRIVE = False
DRIVE_FOLDER  = "/content/drive/MyDrive/PaperOS"

import os, time, struct, random
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {device}")
if device.type == "cuda":
    print(f"GPU: {torch.cuda.get_device_name(0)}")

# ── Model ────────────────────────────────────────────────────────────

class MQA(nn.Module):
    def __init__(self):
        super().__init__()
        self.q_proj = nn.Linear(N_EMBD, N_EMBD,   bias=False)
        self.k_proj = nn.Linear(N_EMBD, HEAD_DIM, bias=False)
        self.v_proj = nn.Linear(N_EMBD, HEAD_DIM, bias=False)
        self.o_proj = nn.Linear(N_EMBD, N_EMBD,   bias=False)

    def forward(self, x):
        B, T, C = x.shape
        q = self.q_proj(x).view(B, T, N_HEAD, HEAD_DIM).transpose(1, 2)
        k = self.k_proj(x).unsqueeze(1).expand(-1, N_HEAD, -1, -1)
        v = self.v_proj(x).unsqueeze(1).expand(-1, N_HEAD, -1, -1)
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        return self.o_proj(y.transpose(1, 2).contiguous().view(B, T, C))


class MLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.c_fc   = nn.Linear(N_EMBD, FF_DIM, bias=False)
        self.c_proj = nn.Linear(FF_DIM, N_EMBD, bias=False)
        nn.init.normal_(self.c_proj.weight, std=0.02 / (2 * N_LAYER) ** 0.5)

    def forward(self, x):
        return self.c_proj(F.gelu(self.c_fc(x), approximate='tanh'))


class Block(nn.Module):
    def __init__(self):
        super().__init__()
        self.ln_1 = nn.LayerNorm(N_EMBD)
        self.attn = MQA()
        self.ln_2 = nn.LayerNorm(N_EMBD)
        self.mlp  = MLP()

    def forward(self, x):
        x = x + self.attn(self.ln_1(x))
        return x + self.mlp(self.ln_2(x))


class TinyGPT(nn.Module):
    def __init__(self):
        super().__init__()
        self.tok_emb = nn.Embedding(VOCAB_SIZE, N_EMBD)
        self.pos_emb = nn.Embedding(CTX_LEN,    N_EMBD)
        self.blocks  = nn.ModuleList([Block() for _ in range(N_LAYER)])
        self.ln_f    = nn.LayerNorm(N_EMBD)
        self.head    = nn.Linear(N_EMBD, VOCAB_SIZE, bias=False)
        self.head.weight = self.tok_emb.weight
        self._init_weights()

    def _init_weights(self):
        nn.init.normal_(self.tok_emb.weight, std=0.02)
        nn.init.normal_(self.pos_emb.weight, std=0.01)
        for m in self.modules():
            if isinstance(m, nn.Linear) and m.weight is not self.tok_emb.weight:
                nn.init.normal_(m.weight, std=0.02)

    def forward(self, x):
        B, T = x.shape
        pos  = torch.arange(T, device=x.device)
        x    = self.tok_emb(x) + self.pos_emb(pos)
        for b in self.blocks:
            x = b(x)
        return self.head(self.ln_f(x))


# ── Dataset ──────────────────────────────────────────────────────────

class BinDataset(Dataset):
    def __init__(self, data, ctx_len):
        self.data    = data
        self.ctx_len = ctx_len
        self.stride  = ctx_len // 2

    def __len__(self):
        return (len(self.data) - self.ctx_len - 1) // self.stride

    def __getitem__(self, idx):
        i = idx * self.stride
        x = torch.from_numpy(self.data[i  :i+self.ctx_len  ].astype(np.int64))
        y = torch.from_numpy(self.data[i+1:i+self.ctx_len+1].astype(np.int64))
        return x, y


def load_datasets():
    import urllib.request
    chunks = []

    # ── TinyStories (~30MB of clean short stories) ───────────────────
    cache = "tinystories.bin"
    if os.path.exists(cache):
        print("TinyStories: from cache")
        chunks.append(np.fromfile(cache, dtype=np.uint8))
    else:
        print("TinyStories: downloading...")
        url = ("https://huggingface.co/datasets/roneneldan/TinyStories"
               "/resolve/main/TinyStories-train.txt")
        urllib.request.urlretrieve(url, "tinystories.txt")
        with open("tinystories.txt", "r", encoding="utf-8", errors="replace") as f:
            text = f.read(30_000_000)
        data = np.frombuffer(text.encode("utf-8", errors="replace"), dtype=np.uint8).copy()
        data.tofile(cache)
        chunks.append(data)
    print(f"  TinyStories: {len(chunks[-1])//1024//1024}MB")

    # ── Chitchat — small, clean, natural ────────────────────────────
    # Interleaved with stories so the model keeps conversational style
    chitchat = [
        ("Hi",                  "Hello! How can I help you today?"),
        ("Hello",               "Hi there! What can I do for you?"),
        ("Hey",                 "Hey! How are you doing?"),
        ("Good morning",        "Good morning! I hope you have a great day."),
        ("Good evening",        "Good evening! How was your day?"),
        ("Good night",          "Good night! Sleep well."),
        ("How are you?",        "I am doing well, thank you for asking!"),
        ("How are you doing?",  "I am good, thanks! How can I help you?"),
        ("What is your name?",  "I am a small AI assistant. You can call me AI."),
        ("Who are you?",        "I am an AI assistant running on a small device."),
        ("What can you do?",    "I can chat with you and tell you stories."),
        ("Thank you",           "You're welcome! Happy to help."),
        ("Thanks",              "No problem, glad I could help!"),
        ("Thank you so much",   "You're welcome! Anytime."),
        ("Sorry",               "No worries, it's all good!"),
        ("Goodbye",             "Goodbye! Take care."),
        ("Bye",                 "Bye! See you later."),
        ("See you later",       "See you! Have a great day."),
        ("Please help me",      "Of course! What do you need help with?"),
        ("Can you help me?",    "Sure, I will do my best to help."),
        ("Are you a robot?",    "Yes, I am an AI running on a small computer."),
        ("Are you human?",      "No, I am an AI assistant, not a human."),
        ("Tell me a story",     "Once upon a time, in a small village, there lived a curious little fox."),
        ("Tell me something",   "Did you know that elephants never forget?"),
        ("I am bored",          "How about a story? Once there was a brave little mouse."),
        ("I am happy",          "That is wonderful to hear!"),
        ("I am sad",            "I am sorry to hear that. I hope things get better soon."),
        ("Yes",                 "Great!"),
        ("No",                  "Alright, no problem."),
        ("Okay",                "Perfect!"),
        ("Cool",                "Glad you think so!"),
        ("Wow",                 "I know, pretty interesting!"),
        ("I agree",             "Glad we agree!"),
        ("I need help",         "I am here to help. What is the problem?"),
        ("Nice to meet you",    "Nice to meet you too!"),
        ("Have a good day",     "Thank you, you too!"),
        ("Take care",           "You too, take care!"),
    ]
    cc_text = "".join(f"Q: {q}\nA: {a}\n\n" for q, a in chitchat) * 200
    cc_data = np.frombuffer(cc_text.encode("utf-8", errors="replace"), dtype=np.uint8).copy()
    chunks.append(cc_data)
    print(f"  Chitchat: {len(chitchat)} pairs x200 = {len(chitchat)*200} examples, "
          f"{len(cc_data)//1024}KB")

    combined = np.concatenate(chunks)
    print(f"\nTotal: {len(combined)//1024//1024}MB")
    return combined


def generate(model, prompt, max_new=60, temp=0.8, top_k=40):
    model.eval()
    ids = torch.tensor([list(prompt.encode())], dtype=torch.long, device=device)
    with torch.no_grad():
        for _ in range(max_new):
            logits = model(ids[:, -CTX_LEN:])[:, -1, :] / temp
            v, _   = torch.topk(logits, top_k)
            logits[logits < v[:, [-1]]] = -float('inf')
            nxt = torch.multinomial(F.softmax(logits, dim=-1), 1)
            ids = torch.cat([ids, nxt], dim=1)
            if nxt.item() == ord('\n') and ids[0, -2].item() == ord('\n'):
                break
    out = ids[0, len(prompt.encode()):].tolist()
    return bytes([b for b in out if 32 <= b < 127 or b == 10]).decode(errors="replace")


def quantize_tensor(w: torch.Tensor):
    """Per-tensor symmetric int8 quant. Matches stream_mv/stream_vec in
    myai_engine.h: out[i] = int8_value * scale (one scale per whole tensor)."""
    arr = w.detach().cpu().numpy().astype(np.float32)
    amax = float(np.abs(arr).max())
    scale = amax / 127.0 if amax > 1e-12 else 1.0
    q = np.round(arr / scale).clip(-127, 127).astype(np.int8)
    return q, scale


def export_model(model, out_path: str) -> float:
    """Writes model.bin in the exact layout myai_engine.h expects:
      header: uint32[6] = vocab, embd, head, layer, ctx, n_tensors (24 bytes)
      then for each tensor: uint32 size_bytes + int8[size_bytes] raw data
      then for each tensor: float32 scale
    Tensor order: tok_emb, pos_emb, per-layer x N_LAYER
    (ln1.w ln1.b Q K V out_proj ln2.w ln2.b ff1 ff2), ln_f.w, ln_f.b, head.
    """
    state = model.state_dict()
    tensors = []

    def add(key):
        q, sc = quantize_tensor(state[key])
        tensors.append((q.reshape(-1), sc))

    add("tok_emb.weight")
    add("pos_emb.weight")
    for l in range(N_LAYER):
        p = f"blocks.{l}."
        add(p + "ln_1.weight"); add(p + "ln_1.bias")
        add(p + "attn.q_proj.weight")
        add(p + "attn.k_proj.weight")
        add(p + "attn.v_proj.weight")
        add(p + "attn.o_proj.weight")
        add(p + "ln_2.weight"); add(p + "ln_2.bias")
        add(p + "mlp.c_fc.weight")
        add(p + "mlp.c_proj.weight")
    add("ln_f.weight"); add("ln_f.bias")
    add("head.weight")

    assert len(tensors) == N_TENSORS, f"got {len(tensors)} tensors, need {N_TENSORS}"

    with open(out_path, "wb") as f:
        f.write(struct.pack("<6I", VOCAB_SIZE, N_EMBD, N_HEAD, N_LAYER, CTX_LEN, N_TENSORS))
        for q, _ in tensors:
            f.write(struct.pack("<I", q.nbytes))
            f.write(q.tobytes())
        for _, sc in tensors:
            f.write(struct.pack("<f", sc))

    return os.path.getsize(out_path) / (1024 * 1024)


def get_lr(step, total_steps):
    if step < WARMUP_STEPS:
        return LR * step / max(WARMUP_STEPS, 1)
    prog = (step - WARMUP_STEPS) / max(total_steps - WARMUP_STEPS, 1)
    return LR/10 + 0.5*(LR - LR/10)*(1 + np.cos(np.pi * prog))


# ── Drive ────────────────────────────────────────────────────────────

if SAVE_TO_DRIVE:
    from google.colab import drive
    drive.mount("/content/drive")
    os.makedirs(DRIVE_FOLDER, exist_ok=True)
    print(f"Drive mounted, saving to {DRIVE_FOLDER}")


# ── Build / resume ───────────────────────────────────────────────────

model = TinyGPT().to(device)

start_epoch = 0
if os.path.exists(CKPT):
    print(f"Resuming from {CKPT}")
    ckpt = torch.load(CKPT, map_location=device)
    state = ckpt.get("model", ckpt)
    model.load_state_dict(state, strict=True)
    start_epoch = ckpt.get("epoch", 0) if isinstance(ckpt, dict) else 0
    print(f"Resumed at epoch {start_epoch}")

total_params  = sum(p.numel() for p in model.parameters())
unique_params = total_params - VOCAB_SIZE * N_EMBD
fwd_kb = (2*VOCAB_SIZE*N_EMBD + N_LAYER*(
    2*N_EMBD + N_EMBD**2 + 2*HEAD_DIM*N_EMBD + N_EMBD**2 +
    2*N_EMBD + 2*FF_DIM*N_EMBD) + 2*N_EMBD + VOCAB_SIZE*N_EMBD) / 1024

print(f"\nParams: {total_params/1e6:.2f}M total, {unique_params/1e6:.2f}M unique")
print(f"Forward reads: {fwd_kb:.0f} KB, ~{fwd_kb*1000/1024:.0f} ms/token")
print(f"~{int(300*1024/fwd_kb)} tokens in 5min timeout")
print(f"KV cache: {N_LAYER*96*2*HEAD_DIM//1024} KB\n")


# ── Data ─────────────────────────────────────────────────────────────

data    = load_datasets()
dataset = BinDataset(data, CTX_LEN)
loader  = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True,
                     num_workers=2, pin_memory=True)

opt    = torch.optim.AdamW(model.parameters(), lr=LR,
                            betas=(0.9, 0.95), weight_decay=0.1)
scaler = torch.amp.GradScaler("cuda")

total_steps  = EPOCHS * len(loader)
global_step  = start_epoch * len(loader)

print(f"Training: {EPOCHS} epochs x {len(loader)} steps = {total_steps} total\n")

TESTS = [
    "Q: Hi\nA:",
    "Q: How are you?\nA:",
    "Q: Thank you\nA:",
    "Q: Tell me a story\nA:",
    "Once upon a time there was",
    "Once upon a time in a forest",
    "There once was a little girl named",
    "The brave knight looked at the",
]


# ── Training loop ────────────────────────────────────────────────────

for epoch in range(start_epoch, EPOCHS):
    model.train()
    total_loss = 0.0
    t0 = time.time()

    for step, (x, y) in enumerate(loader):
        lr = get_lr(global_step, total_steps)
        for g in opt.param_groups:
            g["lr"] = lr

        x, y = x.to(device), y.to(device)
        with torch.amp.autocast("cuda"):
            loss = F.cross_entropy(model(x).view(-1, VOCAB_SIZE), y.view(-1))

        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(opt)
        scaler.update()
        opt.zero_grad(set_to_none=True)

        total_loss  += loss.item()
        global_step += 1

        if step % 200 == 0:
            elapsed = time.time() - t0
            speed   = (step + 1) / max(elapsed, 1e-9)
            eta     = (len(loader) - step) / max(speed, 1e-9)
            print(f"Ep{epoch+1} {step}/{len(loader)} "
                  f"loss={loss.item():.4f} lr={lr:.2e} ETA={eta/60:.0f}min")

        if step % 3000 == 0 and step > 0:
            torch.save({"model": model.state_dict(), "epoch": epoch}, CKPT)
            if SAVE_TO_DRIVE:
                import shutil
                shutil.copy(CKPT, f"{DRIVE_FOLDER}/{CKPT}")

    avg     = total_loss / len(loader)
    elapsed = time.time() - t0
    print(f"\n=== Epoch {epoch+1}/{EPOCHS}  avg_loss={avg:.4f}  time={elapsed/60:.1f}min ===")

    torch.save({"model": model.state_dict(), "epoch": epoch + 1}, CKPT)
    if SAVE_TO_DRIVE:
        import shutil
        shutil.copy(CKPT, f"{DRIVE_FOLDER}/{CKPT}")

    for t in TESTS:
        out = generate(model, t, max_new=40)
        print(f"  {t!r}\n    -> {out.strip()!r}")
    print()


# ── Export ───────────────────────────────────────────────────────────

print("\nExporting model.bin...")
model.eval()
mb = export_model(model, OUT_BIN)

if SAVE_TO_DRIVE:
    import shutil
    shutil.copy(OUT_BIN, f"{DRIVE_FOLDER}/{OUT_BIN}")
    print(f"Saved to {DRIVE_FOLDER}/{OUT_BIN}")

try:
    from google.colab import files
    files.download(OUT_BIN)
    print("Download started.")
except ImportError:
    print(f"File saved: {os.path.abspath(OUT_BIN)}")

print(f"\nDone! model.bin = {mb:.2f} MB")