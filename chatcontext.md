● Thought for 12s...

╰ I should check whether the app/ directory and api\_[server.py](http://server.py) are actually committed to the remote repo, since the README

claims main integrates app/, code/, and idea/ but the timestamps suggest these may be uncommitted local changes. I also

want to verify the TTS models in git LFS and the KBB data are properly tracked.

For naming the folder, the user mentioned "run collab" with a space, which I'll interpret as "run_colab" rather than

literally including a space. I'm thinking through the architecture: a laptop-side launcher script, a VM-side demo script,

and an env file, following the existing pattern where `colab exec` blocks until the script finishes but background

processes started with proper session detachment can persist across exec calls — similar to how ollama serve stays alive

in the existing run\_[all.py](http://all.py) workflow.

I need to make the script idempotent by checking if each service is already running before starting it, since re-runs

happen frequently. For exposing the app, cloudflared's quick tunnel is the best option since it gives HTTPS (needed for

mic access) and works purely from CLI, unlike Colab's proxyPort which needs a notebook browser context. On the Node.js

side, I'm checking whether Colab's preinstalled Node version meets Next.js 16's requirement of >=20.9, and planning to

install via NodeSource if it's outdated, favoring a production build over dev mode for reliability.

I'm weighing whether to attempt `next build` first and fall back to `next dev` if the build fails due to type or lint

errors, keeping things simple. I also want to verify the route handler's Python backend spawning logic, override the

relevant env vars myself, and check whether the app directory and its data/model files are properly tracked and pushed to

the repo, including anything under LFS.

● Shell cd "/run/media/rtx/Files/Study/Semester 5/Minor" && git rev-parse --abbrev-ref HEAD && git remote -v | sed -E

's#//[^@/]+@#//**\*@#' && git status --short | head -30 && echo ---LOG && git log --oneline -5 && echo ---LS && git ls-files

app | head -5 && git ls-files code/demo2/api\_[server.py](http://server.py) code/knowledgebaseenhanced | head -5 && echo --- && cat .gitattributes

2>/dev/null | head; ls code; cat .gitmodules 2>/dev/null

● Shell cd "/run/media/rtx/Files/Study/Semester 5/Minor/code" && ls TTS/chattisgarhi-tts-models TTS/chattisgarhi-tts-models/\*

2>/dev/null | head -30; ls knowledgebaseenhanced/data/kbb/serving 2>/dev/null | head; du -sh knowledgebaseenhanced TTS STT

2>/dev/null; cat Institute-voice-agent/institute-assistant/requirements.txt; ls STT/stt-service; cat

STT/stt-service/requirements.txt 2>/dev/null | head -30

● Thought for 2s...

╰ I'm wondering about the 1.9G of TTS weights — whether they're tracked via Git LFS or live only on the separate

`chattisgarhi-tts-models` branch mentioned in the README, so I should check if best_model.pth is actually included in

main.

● Shell cd "/run/media/rtx/Files/Study/Semester 5/Minor" && git ls-files code/TTS | head; git ls-files code/STT | head -3; git

ls-files code/knowledgebaseenhanced/data | head -5; git ls-files app/voiceagent | grep -E "node_modules|\\.next" | head -2; git

check-ignore -v app/voiceagent/node_modules app/voiceagent/.next code/demo2/.env; git ls-files code/demo2/.env

code/Institute-voice-agent | head -5; git branch -a; git ls-remote --heads origin 2>&1 | sed -E 's#//[^@/]+@#//**\*@#' | head;

grep -n "TTS\\|Coqui\\|best_model\\|import torch\\|from TTS" code/demo2/[speech.py](http://speech.py) | head -30

● Thought for 3s...

╰ I realize the TTS weights (best_model.pth) live in a separate git LFS branch called chattisgarhi-tts-models, not in main

which only has config files. I need to figure out how to pull those weights onto Colab, either via git lfs clone of that

branch or by uploading them directly, so I'm checking the remote branch structure.

● Shell cd "/run/media/rtx/Files/Study/Semester 5/Minor/code/TTS/chattisgarhi-tts-models" && cat [README.md](http://README.md) | head -60; cat

Female/.gitattributes; ls -la Female Male; git -C "/run/media/rtx/Files/Study/Semester 5/Minor" log --oneline -3

chattisgarhi-tts-models; which cloudflared git-lfs 2>&1 | head

● Shell cd "/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2" && sed -n 1,125p [speech.py](http://speech.py); cat

../STT/stt-service/.env.example | head -40; grep -rn "mms\\|facebook" ../STT/stt-service/src/[asr.py](http://asr.py) | head -15

● Thought for 4s...

╰ The TTS weight files (~1GB each) aren't actually on GitHub—the branch the README references doesn't appear in the remote

listing, so those branches must be local only. That means the weights will need to be uploaded directly from the laptop,

roughly 2GB total, which will take some time but is doable.

Mounting Drive from the CLI isn't straightforward, so I'm leaning toward just uploading the .pth files directly since they

won't compress much anyway. I could add an optional download URL env var so the VM pulls weights from a hosted source,

falling back to a launcher-side upload otherwise—but I need to check what commands the Colab CLI actually supports before

deciding how to detect existing weights on the VM.

● Shell export PATH="$HOME/miniconda3/bin:$PATH"; colab --help 2>&1 | head -40; echo ----; colab exec --help 2>&1 | head -30;

echo ----; colab upload --help 2>&1 | head -20; colab status 2>&1 | head

● Shell cd "/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2" && cat .streamlit/config.toml; sed -n 140,260p

api\_[server.py](http://server.py); grep -n "ollama\\|OLLAMA" agent\_[bridge.py](http://bridge.py) | head; node --version; ls

../Institute-voice-agent/institute-assistant | head -30; ls ../Institute-voice-agent/institute-assistant/chroma_index

../Institute-voice-agent/institute-assistant/knowledge_base 2>&1 | head -5

● Thought for 9s...

╰ I notice colab's exec command has a default timeout of only 30 seconds, which is too short, so I should pass \`--timeout

3600\` explicitly. The colab session is likely already idle with the repo cloned and ollama set up from before.

Now I'm thinking through TTS weights for voiceagent — they're only local, so without them the app would still work

text-first but speech would fail. I could upload the weights each fresh VM (~2GB, controllable via an env flag) or mount

them from Drive, then have the launcher check if the model files exist and symlink/copy them into the TTS models folder if

not. I also need to verify what Python/TTS package version the local conda env uses, since Coqui's original TTS package

only supports Python <3.12, while newer Colab images may run 3.12 and need the `coqui-tts` fork instead — checking pip

show on TTS, torch, and transformers in the local env to match.

Since the Colab session is idle, I should just run a quick probe to check Python version, Node version, whether

/content/minor exists, and if TTS is installed, so I have real facts instead of guessing.

● Cancelled export PATH="$HOME/miniconda3/bin:$PATH"; /home/rtx/miniconda3/envs/minor/bin/python -m pip list 2>/dev/null | grep

-iE

"^(tts|coqui|torch|torchaudio|transformers|numpy|fastapi|uvicorn|python-multipart|faster-whisper|ctranslate2|sentence|langgrap

h|langchain|chromadb|soundfile|scipy|streamlit|edge-tts|librosa|numba|silero|pydantic|httpx|rank|bm25|pandas|tokenizers|pytorc

h)" ; colab ls --help 2>&1 | sed -n 1,15p; cd /tmp && cat > /tmp/[probe.py](http://probe.py) <<'EOF'

import sys, subprocess, os

def sh(c):

r=[subprocess.run](http://subprocess.run)(c,shell=True,text=True,capture_output=True); print("$",c,"->",(r.stdout+r.stderr).strip()[:400])

print(sys.version)

for c in ["node --version","npm --version","which cloudflared","ls /content","ls /content/minor | head -3","pip list

2>/dev/null | grep -iE '^(tts|coqui-tts|torch|transformers|numpy|fastapi|uvicorn|python-multipart|tensorflow|jax) '","df -h

/content | tail -1","free -g | head -2","nproc","ollama ps; curl -s localhost:11434/api/version"]: sh(c)

EOF

colab exec -s minor -f /tmp/[probe.py](http://probe.py) --timeout 120 2>&1 | tail -40

────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

what if we zip whole pwd and upload it to colab and then unzip and use it there

● Thought for 3s...

╰ Zipping the whole project directory would capture the TTS weights, uncommitted changes, .env, and kb data without needing

GitHub access, but I should exclude node_modules, .next, **pycache**, .git, and other bulky artifacts to keep the upload

manageable despite the TTS files alone being around 1.9GB. This seems like a reasonable approach to proceed with.

That works well here, and it fixes two problems I just found. The TTS weights (best_model.pth, about 1 GB each) aren't on

GitHub main, and your latest demo2 changes aren't pushed. I'll check what a zip would weigh.

● Shell cd "/run/media/rtx/Files/Study/Semester 5/Minor" && du -sh . 2>/dev/null; du -sh --exclude=node_modules .git app code

idea RTX 2>/dev/null; echo ---; du -sh app/voiceagent/node_modules app/voiceagent/.next code/TTS code/STT

code/knowledgebaseenhanced code/Institute-voice-agent code/demo code/demo2 code/laya-service code/speech2speech_outputs

2>/dev/null; echo ---; du -sh code/Institute-voice-agent/\* 2>/dev/null | sort -h | tail -5; ls -d \*/ ; find . -maxdepth 3

-name "\*.pth" -o -maxdepth 3 -name "\*.safetensors" -o -maxdepth 3 -name "\*.gguf" 2>/dev/null | head

● Thought for 1s...

╰ That demo2 directory being 8.1G seems surprising—I should check if it's data files or evaluation outputs bloating it up.

● Shell cd "/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2" && du -sh _.[a-z]_ 2>/dev/null | sort -h | tail -6; du -sh

data/\* | sort -h | tail -5; cd ../Institute-voice-agent/institute-assistant && du -sh * | sort -h | tail -5

● Thought for 10s...

╰ I'm weighing whether to exclude the large upgrade directory and the kb_state folder, since demo2 defaults to the KBB

serving backend and kb_state seems only relevant for the legacy path—though I need to check that the active release logic

doesn't still depend on it before deciding to leave it out.

I'm estimating the bundle size: TTS weights are the big fixed cost at 1.9GB, plus a lean code slice without node_modules

or build artifacts, giving roughly 2.5GB total if I also drop laya-service and other junk directories. To make iteration

faster, I'm planning to split this into two zips—a small code bundle for frequent re-uploads and a separate large TTS

weights bundle only uploaded once—and I'll just use Python's zipfile on both ends since unzip is available on the VM.

I also need to check what's in the local .env files since they might contain absolute paths or API keys that shouldn't

leak, and I'm sketching the file layout: a laptop-side script to build and upload bundles, a VM-side script to unzip and

start services, and deciding to skip a separate README in favor of inline usage notes in the scripts themselves.

● Shell cd "/run/media/rtx/Files/Study/Semester 5/Minor/code" && sed -E

's/(KEY|TOKEN|PASSWORD|SECRET)[A-Z\_]\*=.+/\1…=\<redacted>/' demo2/.env | grep -v '^#' | grep -v '^$'; echo ----; ls -a

Institute-voice-agent/institute-assistant/.env STT/stt-service/.env 2>&1; sed -E 's/=.\*(gsk\_|sk-).\*/=\<redacted>/'

Institute-voice-agent/institute-assistant/.env 2>/dev/null | grep -v '^#' | grep -v '^$' | cut -c1-90; cat

Institute-voice-agent/institute-assistant/setup\_[local.py](http://local.py) | sed -n 1,40p; grep -n "def

configure_agent\\|requirements\\|python-multipart" demo2/api\_[server.py](http://server.py) | head -3; grep -n "import" ../app/voiceagent/lib/\*.ts

2>/dev/null | head -3

● Thought for 6s...

╰ I notice institute-assistant/.env holds live secrets like the GROQ and OPENJEV keys, so I should exclude all .env files

from the bundle to avoid shipping credentials in the zip. Instead, I'll have the launcher send a separate colab.env, and

have the VM reconstruct demo2/.env from safe defaults plus that colab.env.

I should also exclude the STT service's .env for the same reason, and avoid repeating any secret values I've already seen.

For vm\_[run.py](http://run.py), I need to make the script idempotent since it runs via exec with a timeout but must leave background

services alive across invocations—processes started with nohup/start_new_session likely survive since the kernel persists.

I also need to confirm the Python environment has all required packages (fastapi, uvicorn, python-multipart, coqui TTS) by

rerunning pip list locally since my earlier check was cancelled.

● Shell /home/rtx/miniconda3/envs/minor/bin/python -m pip list 2>/dev/null | grep -iE

"^(tts|coqui|torch|torchaudio|transformers|numpy|fastapi|uvicorn|python-multipart|faster-whisper|ctranslate2|sentence-transfor

mers|langgraph|chromadb|soundfile|scipy|librosa|numba|silero-vad|pydantic|rank-bm25|pandas|tokenizers|trainer|gruut|jieba|pypi

nyin|spacy|edge-tts|espeak|phonemizer|inflect|anyascii|unidecode|num2words) " ; /home/rtx/miniconda3/envs/minor/bin/python

\--version; grep -n "^import\\|^from" "/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/agent\_[bridge.py](http://bridge.py)"

"/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/[jobs.py](http://jobs.py)" | grep -viE "import (os|re|json|time|sys|io|asyncio)$" | head

-30

● Thought for 11s...

╰ I need to account for version compatibility: locally I'm pinning TTS 0.22.0 with numpy 1.26.4 and transformers 4.46.1

since Python needs to stay under 3.12, but on Colab with Python 3.12 and numpy 2.x that same package install breaks, so I

should use the coqui-tts fork instead.

The API surface looks mostly compatible but I'm uncertain whether `use_cuda` param in the Synthesizer still works across

coqui-tts versions, which makes mixing environments risky. The safest bet is probably to replicate my local Python 3.11

setup exactly on Colab using uv to create a matching venv, even though that means a slow torch/CUDA download, since that's

the environment I've actually verified passes all 316 tests.

I'm settling on pinned versions: TTS 0.22.0, transformers 4.46.1, numpy 1.26.4, plus fastapi/uvicorn pins, letting TTS

resolve its own pandas dependency rather than over-specifying, and forcing this venv at a fixed path regardless of

whatever Python version Colab ships by default.

One concern though: newer torch versions default `torch.load` to `weights_only=True`, which could break Coqui's checkpoint

loading since 0.22 wasn't written with that in mind. My local setup uses torch 2.13 and it works fine, so the repo must be

handling this somehow -- I should grep for `weights_only` in the codebase to confirm rather than guessing a torch pin.

● Shell cd "/run/media/rtx/Files/Study/Semester 5/Minor/code" && grep -rn "weights_only" --include=\*.py demo2 STT TTS

Institute-voice-agent 2>/dev/null | head -5; sed -n 186,225p demo2/[speech.py](http://speech.py); /home/rtx/miniconda3/envs/minor/bin/python -c

"import torch;print(torch.\__version\_\_, torch.version.cuda)"; export PATH="$HOME/miniconda3/bin:$PATH"; which uv

● Thought for 26s...

╰ I'm puzzled why torch 2.13 locally works with TTS 0.22's loading mechanism despite newer torch defaults potentially

breaking unpickling—there may be some patch at play. To be safe, I should try matching the exact local environment

versions on the VM, though I'm unsure if that torch version is even available there.

Given Colab's A100 driver likely supports CUDA 12.x rather than 13, I'd better avoid relying on default PyPI torch wheels

built for cu13 and instead target a CUDA 12.4 index with an older, known-stable torch like 2.5.1, which avoids the

weights_only default issue entirely and is a proven compatible era for TTS 0.22. For STT, setting the device to "auto" is

safer since it falls back to CPU on failure, and keeping TTS on CPU minimizes GPU-related risk altogether—GPU really only

matters for the experimental MMS component.

Since I can't fully verify compatibility without an actual Colab run, I'll proceed carefully and plan to test what's

testable locally—bundle creation, script syntax, and dry-run unzip logic—while leaving long GPU verification for the user

to run later, per the project's convention that the user handles long/GPU tests. I also need to account for Node.js:

Colab's shipped version is uncertain, so I should install Node 22 via NodeSource if the existing version is missing or

outdated.

For the tunnel, I'll download cloudflared directly from GitHub releases and run it to expose the local Next.js server,

extracting the generated [trycloudflare.com](http://trycloudflare.com) URL from logs. I should flag that this creates a public, unauthenticated

endpoint—anyone with the URL could access the app and use GPU resources, though the randomness of the URL offers some

protection; I'll mention this as a caveat rather than building in extra auth.

For the Next.js app itself, I'm planning the build and run sequence: install dependencies, build, then start the server

bound to localhost with the right environment variables pointing to the API and Python venv, falling back to dev mode if

the build fails. Now I'm checking the package.json to confirm build tooling details.

For the backend, I'll run uvicorn locally with environment variables and logging configured, and I'm working out the right

.env overrides for the demo—specifically deciding whether to bump up the Ollama context window beyond what was used in

testing, settling on a larger context size since the GPU has plenty of headroom and it only relaxes memory budgeting

rather than risking anything.

I also need to handle Ollama installation, pulling the model if it's not already present, and setting the right

host/keep-alive environment variables. For speech-to-text, I'm considering pre-warming the Whisper model download so the

first microphone request isn't slow, plus checking on the MMS model needed for the other language.

For retrieval, I'm weighing whether to pre-download the embedding model too, but that first-query slowdown is probably

acceptable to just leave as-is rather than adding complexity to warm it up.

For running the server, I'll launch it as a detached subprocess with its own session and log file so it persists

independently of the script's execution. I also need to think about idempotency so repeated runs don't conflict when

replacing the bundle.

On rerun I should kill the existing backend/frontend processes first, then extract the fresh code into a separate run

directory, clearing out `.next` but preserving `node_modules` unless the lockfile changed, and I need to exclude the demo2

data directory (which holds old conversation databases) so it doesn't get wiped but still gets recreated at runtime.

I also need to figure out which other directories to exclude from the bundle -- things like `.git`, caches, `.env` files,

and the large `kb_state` directory, while checking whether the legacy KB_BACKEND path actually depends on that state

existing.

Let me check how kb_state is referenced to decide if it's safe to drop.

● Shell cd "/run/media/rtx/Files/Study/Semester 5/Minor/code" && grep -rn "kb_state\\|KB_STATE_DIR" --include=\*.py demo2/\*.py

Institute-voice-agent/institute-assistant/assistant | head -15; ls Institute-voice-agent/institute-assistant/kb_state | head;

ls knowledgebaseenhanced/data/kbb/serving knowledgebaseenhanced/data/kbb/serving/releases 2>/dev/null | head; du -sh

knowledgebaseenhanced/data/kbb/serving; grep -n "OLLAMA_TOKENIZER_PATH" -r

Institute-voice-agent/institute-assistant/assistant/[config.py](http://config.py)

● Thought for 41s...

╰ I'm figuring out which directories under kb_state to exclude from the backup—backups, embedding_cache, assets,

extracted—while keeping active.json, and planning to skip any file over 50MB in the code tree except TTS-related files.

I'm compiling the full exclusion list now: common dev clutter like .git, node_modules, .next, caches, plus specific

project paths that are too large or irrelevant (demo outputs, notebooks, run_colab artifacts). I'm keeping chroma_index

and the evaluation outputs since they're reasonably sized, and noting the backup needs to target the correct root

directory under the "Minor" project folder.

Since colab uploads may struggle with files over 1GB, I'm planning to split the TTS model zip into smaller chunks (around

200MB each) with filenames like part000, part001, etc., so they can be uploaded individually with retries and then

reassembled on the VM side. I'll build this chunking logic into the launcher script.

I also need a way to check if the TTS models are already present on the VM to avoid redundant uploads — probably by

running a small check script via `colab exec` that prints a status marker I can grep for, plus a `SKIP_TTS` flag for

text-only runs. I'm also reconsidering whether to write the launcher in Python instead of bash, since Python handles

chunking and quoting more cleanly.

I'm settling on a design where [`launch.py`](http://launch.py) runs on the laptop, with a thin [`run.sh`](http://run.sh) wrapper that locates it, and

everything else — bundling code, uploading env files, checking/uploading TTS models, and pushing `vm_`[`run.py`](http://run.py) — happens

inside [`launch.py`](http://launch.py) so it can be rerun later via exec without relaunching the session.

After the exec call finishes, I'll tail output for the printed URL and also pull `public_url.txt` back down to

`run_colab/last_url.txt`, streaming prints along the way since the subprocess runs long and stays in the background. For

`vm_`[`run.py`](http://run.py), I'm sketching the directory layout (venv, app root, logs) and the startup sequence: load env vars, check GPU,

then stop any old services like uvicorn, next start, and cloudflared before deciding whether a new tunnel URL is needed.

For keeping the URL stable, I think it's better to leave the cloudflared tunnel running if it's already pointed at the

same local port, rather than killing everything and generating a fresh URL each run. Then I unzip the code bundle into

place, and for the TTS models I either concatenate split parts into a models zip and extract them, or fall back to a

cached copy if the marker exists but the directory is missing — storing the actual model weights persistently and

symlinking them into the code bundle's TTS directory, while keeping the config.json shipped separately in the code bundle

itself.

For setting up the Python environment, I'm planning to install uv if it's missing, create a venv, and gate reinstallation

behind a hash marker of the package list. Torch and torchaudio need to come from the CUDA 12.4 wheel index first, and I'm

working through whether that index also mirrors the necessary dependencies like sympy, networkx, jinja2, and the nvidia

packages so that a strict single-index install won't break.

I realize PyPI's default Linux torch 2.5.1 wheel already bundles CUDA 12.4 dependencies, so I can simplify by just

installing torch and torchaudio straight from PyPI without needing the special index at all. Now I'm checking

compatibility between torch 2.5.1, numpy 1.26.4, and Python 3.11, then working out the right numpy version pin for TTS

0.22.0 alongside transformers 4.46.1.

For the demo2 requirements, I want to skip streamlit entirely since it's not needed, but first I need to verify none of

the api_server modules (workflow, jobs, speech, storage, verbalization) actually import it before dropping it from the

install.

I'm pinning numpy, transformers, torch, and torchaudio versions in a constraints file to keep them compatible with the

existing tokenizers version, then listing out the remaining core deps like fastapi, uvicorn, edge-tts, faster-whisper, and

silero-vad that the STT source actually imports.

Checking whether rank-bm25 is actually installed locally—it's not in the pip list despite being mentioned in the README,

so I'm treating it as unnecessary. I'm also confirming ctranslate2's GPU requirements align with the cuDNN/cuBLAS versions

that come bundled with the pinned torch build.

I need to set LD_LIBRARY_PATH to point at the venv's nvidia site-packages lib directories so ctranslate2 can actually find

those libraries at runtime, since the fallback-to-CPU logic already handles the RuntimeError case if the libraries are

missing. Then I'll prewarm the model by downloading the "small" faster-whisper model using the venv's python.

For Ollama, I'm keeping setup the same as before, and for the tokenizer I'm handling it via setup\_[local.py](http://local.py) with its own

environment variables. Rather than writing a .env file (which the backend might not reliably pick up before the venv env

vars take priority), I'll pass environment variables directly when spawning the backend process via Popen, including

provider settings, device configs, routing mode, API keys if present, and the LD_LIBRARY_PATH I computed. For TTS, I'm

considering whether to run VITS on GPU instead of CPU given the A100 box's limited CPU core count would make CPU synthesis

slower.

I'm deciding to keep TTS on CPU as the tested, reliable default even though GPU would be faster, since switching voices

would evict the GPU cache; I'll leave it configurable via an override in colab.env. Then for starting the backend, I'm

using Popen to launch uvicorn and polling the health endpoint for up to 120 seconds, followed by handling the Node app:

checking if node_modules needs reinstalling, running the build, and falling back to dev mode if the build fails, while

watching for port conflicts with Colab's own services.

After that, I'm setting up the cloudflared tunnel to get a public URL and verifying the health endpoint responds through

it, accounting for possible DNS propagation delay with retries, then writing the final public URL to a file in the output

directory and printing a summary. I also need to think through how the "stop" mode should behave for tearing things down.

For the stop action, I'm realizing I can pass an ACTION=stop environment variable through the exec command's built-in env

flag rather than building a separate mechanism, and I'll have vm\_[run.py](http://run.py) read that variable and immediately pop it from

os.environ afterward so it doesn't leak into later kernel sessions. Now I want to check how streamlit gets used elsewhere

in the demo2 codebase outside the app module.

● bash echo

A tool with the name 'bash' does not exist

● Grep "^\s\*(import|from) (streamlit|rank_bm25|laya)"

╰ path=/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2, include=\*.py, output_mode=files_with_matches

3 matches in 3 files

● Grep "health|status|^def |^@app\\.(get|post)"

╰ path=/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2, include=api\_[server.py](http://server.py), max_matches_per_file=40

75 matches in 1 file (showing first results)

● Thought for 1s...

╰ Streamlit is only referenced in [app.py](http://app.py) and tests, so I'll skip installing it since it's unnecessary overhead. Time to

start writing the files.

Streamlit is only used by [app.py](http://app.py) and the tests, so the API stack doesn't need it. Writing the files now.

● Write /run/media/rtx/Files/Study/Semester 5/Minor/run_colab/[launch.py](http://launch.py)

added 229 lines in [launch.py](http://launch.py)

1+ #!/usr/bin/env python3

2+ """

3+ [launch.py](http://launch.py) -- run on your LAPTOP. Zips this project, uploads it to a Colab GPU session

4+ and starts Demo 2 (FastAPI backend) + the Next.js web app there, behind a public HTTPS URL.

5+

6+ python3 run_colab/[launch.py](http://launch.py) # build zip, upload, start everything

7+ python3 run_colab/[launch.py](http://launch.py) --stop # stop backend / web app / tunnel on the VM

8+ python3 run_colab/[launch.py](http://launch.py) --no-tts # skip the ~2 GB TTS voice upload (text answers only)

9+ python3 run_colab/[launch.py](http://launch.py) --rebuild-tts # force re-upload of the TTS voices

10+

11+ What gets uploaded

12+ code\_[bundle.zip](http://bundle.zip) source of app/voiceagent + code/{demo2,Institute-voice-agent,knowledgebaseenhanced,

13+ STT,TTS configs} (small; re-uploaded every run, so your latest local edits are used)

14+ tts_models parts the two Chhattisgarhi VITS checkpoints (~2 GB). Uploaded ONCE per Colab VM in

15+ 200 MB parts; later runs detect them on the VM and skip.

16+ Never uploaded: any .env (API keys), .git, node_modules, .next, caches, demo2/data (8 GB of old runs),

17+ laya-service, the agri demo, idea/, RTX/.

18+ """

19+ import argparse

20+ import os

21+ import shutil

22+ import subprocess

23+ import sys

24+ import tempfile

25+ import zipfile

26+ from pathlib import Path

27+

28+ HERE = Path(\__file\_\_).resolve().parent

29+ PROJECT = HERE.parent # .../Minor

30+ DIST = HERE / "dist"

31+ SESSION = os.environ.get("COLAB_SESSION", "minor")

32+ GPU = os.environ.get("COLAB_GPU", "A100")

33+ PART_BYTES = 200 _1024 <!---->_<!---->1024

34+ UPLOAD_TIMEOUT = 1800

35+

36+ # --- what goes in the code bundle ------------------------------------------------------------

37+ INCLUDE_ROOTS = [

38+ "app/voiceagent",

39+ "code/demo2",

40+ "code/Institute-voice-agent",

41+ "code/knowledgebaseenhanced",

42+ "code/STT",

43+ "code/TTS", # configs/scripts only; weights are handled separately

44+ ]

45+ EXCLUDE_DIR_NAMES = {".git", "node_modules", ".next", "\__pycache\_\_", ".pytest_cache", ".venv", "venv",

46+ ".mypy_cache", ".ruff_cache"}

47+ EXCLUDE_PREFIXES = [ # project-relative posix paths

48+ "code/demo2/data", # 8 GB of old evaluation runs + live sqlite state

49+ "code/Institute-voice-agent/institute-assistant/kb_state", # legacy KB; demo2 uses the kbb release

50+ "code/Institute-voice-agent/voice-orchestrator",

51+ ]

52+ EXCLUDE_SUFFIXES = (".pyc", ".pth", ".wav", ".log", ".pid", ".ipynb")

53+ EXCLUDE_FILE_NAMES = {".env"} # secrets stay on the laptop; VM gets /content/.env instead

54+ TTS_REL = "code/TTS/chattisgarhi-tts-models"

55+ VOICES = ("Female", "Male")

56+

57+

58+ def log(msg):

59+ print(f"[launch] {msg}", flush=True)

60+

61+

62+ def find_colab():

63+ exe = shutil.which("colab")

64+ if exe:

65+ return exe

66+ for d in (Path.home() / "miniconda3/bin", Path.home() / "anaconda3/bin", Path.home() / ".local/bin"):

67+ if (d / "colab").exists():

68+ return str(d / "colab")

69+ sys.exit("[launch] colab CLI not found (install: uv tool install google-colab-cli)")

70+

71+

72+ COLAB = find_colab()

73+

74+

75+ def colab(\*args, check=True, capture=False, timeout=None):

76+ cmd = [COLAB, \*args]

77+ if capture:

78+ return [subprocess.run](http://subprocess.run)(cmd, text=True, capture_output=True, timeout=timeout)

79+ rc = [subprocess.run](http://subprocess.run)(cmd, timeout=timeout).returncode

80+ if check and rc != 0:

81+ sys.exit(f"[launch] command failed ({rc}): {' '.join(cmd)}")

82+ return rc

83+

84+

85+ def ensure_session():

86+ r = colab("status", "-s", SESSION, capture=True, check=False)

87+ if SESSION in (r.stdout or "") and "Hardware:" in (r.stdout or ""):

88+ log(f"session '{SESSION}' exists")

89+ return

90+ log(f"creating session '{SESSION}' ({GPU})")

91+ colab("new", "-s", SESSION, "--gpu", GPU)

92+

93+

94+ def skip(rel: Path, is_dir=False):

95+ posix = [rel.as](http://rel.as)\_posix()

96+ if any(part in EXCLUDE_DIR_NAMES for part in [rel.parts](http://rel.parts)):

97+ return True

98+ if any(posix == p or posix.startswith(p + "/") for p in EXCLUDE_PREFIXES):

99+ return True

100+ if not is_dir and ([rel.name](http://rel.name) in EXCLUDE_FILE_NAMES or [rel.name](http://rel.name).endswith(EXCLUDE_SUFFIXES)):

101+ return True

102+ return False

103+

104+

105+ def build_code_zip() -> Path:

106+ DIST.mkdir(exist_ok=True)

107+ out = DIST / "code\_[bundle.zip](http://bundle.zip)"

108+ count = 0

109+ with zipfile.ZipFile(out, "w", [zipfile.ZIP](http://zipfile.ZIP)\_DEFLATED, compresslevel=6) as zf:

110+ for root in INCLUDE_ROOTS:

111+ base = PROJECT / root

112+ if not base.exists():

113+ log(f"WARNING: {root} not found, skipped")

114+ continue

115+ for dirpath, dirnames, filenames in os.walk(base):

116+ rel_dir = Path(dirpath).relative_to(PROJECT)

117+ dirnames[:] = [d for d in dirnames if not skip(rel_dir / d, is_dir=True)]

118+ for name in filenames:

119+ rel = rel_dir / name

120+ if skip(rel):

121+ continue

122+ path = PROJECT / rel

123+ if [path.is](http://path.is)\_symlink() or not [path.is](http://path.is)\_file():

124+ continue

125+ zf.write(path, [rel.as](http://rel.as)\_posix())

126+ count += 1

127+ log(f"code\_[bundle.zip](http://bundle.zip): {count} files, {out.stat().st_size / 1e6:.1f} MB")

128+ return out

129+

130+

131+ def tts_on_vm() -> bool:

132+ probe = (

133+ "from pathlib import Path\n"

134+ "ok = all(Path('/content/tts_models/%s/best_model.pth' % v).is_file() for v in ('Female','Male'))\n"

135+ "print('TTS_ON_VM=' + ('yes' if ok else 'no'))\n"

136+ )

137+ with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:

138+ f.write(probe)

139+ name = [f.name](http://f.name)

140+ try:

141+ r = colab("exec", "-s", SESSION, "-f", name, "--timeout", "120", capture=True, check=False)

142+ finally:

143+ os.unlink(name)

144+ return "TTS_ON_VM=yes" in ((r.stdout or "") + (r.stderr or ""))

145+

146+

147+ def upload_tts():

148+ sources = []

149+ for v in VOICES:

150+ ckpt = PROJECT / TTS_REL / v / "best_model.pth"

151+ if not [ckpt.is](http://ckpt.is)\_file() or ckpt.stat().st_size < 1_000_000:

152+ log(f"WARNING: {ckpt} missing or a Git-LFS pointer; TTS voices will not work")

153+ return False

154+ sources.append((v, ckpt))

155+ zpath = DIST / "tts\_[models.zip](http://models.zip)"

156+ log("packing TTS checkpoints (stored, no compression)...")

157+ with zipfile.ZipFile(zpath, "w", [zipfile.ZIP](http://zipfile.ZIP)\_STORED) as zf:

158+ for v, ckpt in sources:

159+ zf.write(ckpt, f"{v}/best_model.pth")

160+ total = zpath.stat().st_size

161+ parts = -(-total // PART_BYTES)

162+ log(f"uploading {total / 1e9:.2f} GB in {parts} parts of 200 MB (one-time per VM)")

163+ part_dir = DIST / "tts_parts"

164+ shutil.rmtree(part_dir, ignore_errors=True)

165+ part_dir.mkdir()

166+ with open(zpath, "rb") as src:

167+ for i in range(parts):

168+ part = part_dir / f"[tts.zip](http://tts.zip).part{i:03d}"

169+ part.write_bytes([src.read](http://src.read)(PART_BYTES))

170+ for attempt in (1, 2, 3):

171+ rc = colab("upload", "-s", SESSION, str(part), f"/content/tts_parts/{[part.name](http://part.name)}",

172+ check=False, timeout=UPLOAD_TIMEOUT)

173+ if rc == 0:

174+ break

175+ log(f" part {i + 1}/{parts} failed (attempt {attempt}/3)")

176+ else:

177+ sys.exit(f"[launch] could not upload {[part.name](http://part.name)}")

178+ part.unlink()

179+ log(f" part {i + 1}/{parts} done")

180+ shutil.rmtree(part_dir, ignore_errors=True)

181+ zpath.unlink()

182+ return True

183+

184+

185+ def main():

186+ ap = argparse.ArgumentParser()

187+ ap.add_argument("--stop", action="store_true", help="stop the services on the VM and exit")

188+ ap.add_argument("--no-tts", action="store_true", help="do not upload TTS voice checkpoints")

189+ ap.add_argument("--rebuild-tts", action="store_true", help="re-upload TTS even if present on the VM")

190+ ap.add_argument("--timeout", type=int, default=3300, help="seconds allowed for the VM setup run")

191+ args = ap.parse_args()

192+

193+ ensure_session()

194+ vm_script = HERE / "vm\_[run.py](http://run.py)"

195+

196+ if args.stop:

197+ colab("exec", "-s", SESSION, "-f", str(vm_script), "--timeout", "300", "--env", "ACTION=stop")

198+ return

199+

200+ code_zip = build_code_zip()

201+

202+ env_file = HERE / "colab.env"

203+ if env\_[file.is](http://file.is)\_file():

204+ colab("upload", "-s", SESSION, str(env_file), "/content/.env", check=False)

205+

206+ if not [args.no](http://args.no)\_tts:

207+ if args.rebuild_tts or not tts_on_vm():

208+ upload_tts()

209+ else:

210+ log("TTS checkpoints already on the VM -> skipping upload")

211+

212+ log("uploading code bundle")

213+ colab("upload", "-s", SESSION, str(code_zip), "/content/code\_[bundle.zip](http://bundle.zip)", timeout=UPLOAD_TIMEOUT)

214+

215+ log("starting Demo 2 + web app on the VM (first run on a fresh VM takes ~10-15 min)")

216+ rc = colab("exec", "-s", SESSION, "-f", str(vm_script), "--timeout", str(args.timeout),

217+ "--env", "ACTION=run", check=False)

218+

219+ url_file = HERE / "public_url.txt"

220+ colab("download", "-s", SESSION, "/content/colab_out/public_url.txt", str(url_file), check=False)

221+ if url\_[file.is](http://file.is)\_file():

222+ log(f"OPEN THIS URL: {url\_[file.read](http://file.read)\_text().strip()}")

223+ else:

224+ log("no public URL was produced; check the output above and /content/colab_out/\*.log on the VM")

225+ sys.exit(rc)

226+

227+

228+ if **name** == "\__main\_\_":

229+ main()

● Write /run/media/rtx/Files/Study/Semester 5/Minor/run_colab/colab.env

added 19 lines in colab.env

1+ # Settings for the Colab VM (uploaded as /content/.env by [launch.py](http://launch.py)). All optional.

2+ # Real keys belong here only -- this file is never zipped into code\_[bundle.zip](http://bundle.zip).

3+

4+ # Ollama model for reasoning (already benchmarked on the A100).

5+ MODEL_TAG=qwen3.5:9b

6+ OLLAMA_NUM_CTX=16384

7+

8+ # Optional: lets the UI select Groq cloud reasoning instead of local Ollama.

9+ GROQ_API_KEY=

10+

11+ # Speech devices. auto = Whisper on GPU, falling back to CPU if CUDA libs are unusable.

12+ # Set DEMO2_TTS_DEVICE=cuda for faster voice synthesis (only one voice stays cached on GPU).

13+ DEMO2_STT_DEVICE=auto

14+ DEMO2_TTS_DEVICE=cpu

15+ DEMO2_WHISPER_MODEL=small

16+

17+ # Ports on the VM (the public URL always maps to WEB_PORT).

18+ WEB_PORT=3001

19+ API_PORT=8020

● Thought for 30s...

╰ Now I'm designing vm\_[run.py](http://run.py) as pure stdlib Python 3.12 code, with a streaming shell runner that prints output

line-by-line, a background process launcher using detached sessions, a health-check helper, and a function to stop

services by killing matching processes.

For stopping services, I need pkill patterns matching uvicorn, Next.js start/dev servers, and cloudflared — using

subprocess with list args so pkill doesn't match itself. The code bundle gets unzipped without deleting old files, keeping

node_modules cached across runs but leaving stale files from removed sources, which I'll accept as fine; I'll always

rebuild `.next` since the build is fast enough rather than trying to hash-check for changes. I'm writing the TTS asset

staging logic that checks for cached model files and assembles them from split zip parts if missing.

Writing symlink and extraction logic...

I realize the env file loading needs fixing: rather than writing parsed values directly into os.environ (which would let

stale values from earlier kernel runs persist and block updates to colab.env), I should parse into a separate config dict

and read through a helper function that prefers fresh values.

Now I'm sketching the virtual environment setup using uv for Python 3.11, then breaking the dependency installs into

separate calls (torch/torchaudio, TTS/transformers/numpy, demo requirements, assistant requirements with a shared

constraints file) so failures are easier to isolate.

Checking version compatibility across the stack—numpy 1.26.4, transformers 4.46.1, torch/torchaudio 2.5.1, tokenizers

under 0.21, plus langchain-core, langgraph, chromadb, opencv-headless, and pandas pinned to work with TTS's older pandas

requirement—to make sure nothing conflicts.

I'm now reviewing extras like fastapi, uvicorn, pydantic, edge-tts, soundfile, scipy, faster-whisper, and silero-vad,

deciding what to pin versus leave unresolved based on what's actually imported in the codebase. Since I can't run a live

install to verify everything resolves, I'm considering adding a post-install smoke test that imports key modules to catch

any missing dependencies early.

For the Ollama setup, I'm sketching out a function that checks if the binary exists, installs zstd and the Ollama CLI if

needed, and verifies the service is reachable before proceeding.

I also want to warm the model onto the GPU with a generate call before the agent makes its real request, since mismatched

context sizes (16384 vs the default) force a reload on the first real call — so I should match the num_ctx option in the

warm-up to avoid that delay.

I'm also running the local tokenizer setup script non-fatally, then putting together the backend environment variables for

Ollama, deciding whether to carry over something like a num_predict setting from the Colab env file.

I'm setting other demo-specific environment variables like code root, STT/TTS device, Whisper model, and speech thread

count tuned to Colab's core count, along with routing mode and threading flags. I'm also wondering if the kernel's

inherited environment variables, like PYTHONPATH, could leak Colab's system packages into the venv's Python process.

Right, Colab sets PYTHONPATH to its own env directory, so I need to strip PYTHONPATH, PYTHONHOME, and VIRTUAL_ENV from the

child process environment to avoid contamination. For starting the backend, I'll run uvicorn from the DEMO2 directory on

the configured port and poll the health endpoint for up to 180 seconds, printing log tails if it fails -- and I need to

make sure the Next.js respawn logic inherits the same sanitized environment so a backend crash and restart doesn't lose

these settings.

For Node, I'm checking the installed version meets the minimum (20.9+) and installing via NodeSource's setup script if

not, then running npm ci and a production build with telemetry disabled, falling back to dev mode if the build fails. For

exposing the app publicly, I'm writing logic to check if a cloudflared tunnel is already running and healthy, otherwise

killing any stale process, downloading the binary, and launching a fresh tunnel pointed at the local port while logging

output to a file.

I'm also adding retry logic to verify the health endpoint through the tunnel URL, since trycloudflare can briefly return

errors or get blocked without a proper User-Agent header, and handling the ACTION environment variable along with final

status printing, GPU info logging, and flushed streaming output -- all while keeping total runtime comfortably under the

execution limit.

● Write /run/media/rtx/Files/Study/Semester 5/Minor/run_colab/vm\_[run.py](http://run.py)

added 391 lines in vm\_[run.py](http://run.py)

1+ #!/usr/bin/env python3

2+ """

3+ vm\_[run.py](http://run.py) -- runs ON the Colab VM (sent there by [`launch.py`](http://launch.py) via `colab exec`).

4+

5+ Pure Python on purpose: `colab exec` hands the file to the Colab _Python_ kernel, so bash scripts

6+ cannot be used. Everything is idempotent -- re-running only redoes what changed:

7+

8+ 1. unpack /content/code\_[bundle.zip](http://bundle.zip) -> /content/minor_run

9+ 2. link the TTS voice checkpoints (/content/tts_models, uploaded once by [launch.py](http://launch.py))

10+ 3. Python 3.11 venv (uv) with the same stack as the local `minor` conda env

11+ 4. Ollama (GPU) + model, tokenizer for the agent

12+ 5. Demo 2 FastAPI backend -> 127.0.0.1:API_PORT

13+ 6. Node + Next.js app build -> 127.0.0.1:WEB_PORT (proxies /api/py/\* to the backend)

14+ 7. Cloudflare quick tunnel -> public HTTPS URL (HTTPS is required for browser microphone access)

15+

16+ Result URL: printed at the end and saved to /content/colab_out/public_url.txt

17+ Stop everything: python3 run_colab/[launch.py](http://launch.py) --stop

18+ """

19+ import hashlib

20+ import json

21+ import os

22+ import re

23+ import shutil

24+ import subprocess

25+ import sys

26+ import time

27+ import urllib.request

28+ import zipfile

29+ from pathlib import Path

30+

31+ ROOT = Path("/content/minor_run")

32+ APP = ROOT / "app/voiceagent"

33+ DEMO2 = ROOT / "code/demo2"

34+ AGENT = ROOT / "code/Institute-voice-agent/institute-assistant"

35+ TTS_DIR = ROOT / "code/TTS/chattisgarhi-tts-models"

36+ TTS_CACHE = Path("/content/tts_models")

37+ TTS_PARTS = Path("/content/tts_parts")

38+ BUNDLE = Path("/content/code\_[bundle.zip](http://bundle.zip)")

39+ VENV = Path("/content/venv311")

40+ PY = VENV / "bin/python"

41+ LOGS = Path("/content/colab_out")

42+ OLLAMA_URL = "http://127.0.0.1:11434"

43+ VOICES = ("Female", "Male")

44+

45+ # Mirrors the local, test-verified `minor` conda env (Python 3.11, numpy 1.26, TTS 0.22, transformers 4.46).

46+ CONSTRAINTS = ["numpy==1.26.4", "transformers==4.46.1", "torch==2.5.1", "torchaudio==2.5.1", "tokenizers<0.21"]

47+ PKG_TORCH = ["torch==2.5.1", "torchaudio==2.5.1"]

48+ PKG_TTS = ["TTS==0.22.0", "transformers==4.46.1", "numpy==1.26.4"]

49+ PKG_DEMO2 = ["fastapi==0.115.6", "uvicorn[standard]==0.34.0", "python-multipart", "edge-tts==7.2.8",

50+ "soundfile>=0.12", "scipy>=1.11", "python-dotenv>=1.0", "faster-whisper==1.2.1", "silero-vad==6.2.1"]

51+ DEPS_VERSION = hashlib.sha256(json.dumps([CONSTRAINTS, PKG_TORCH, PKG_TTS, PKG_DEMO2]).encode()).hexdigest()[:16]

52+

53+

54+ # --------------------------------------------------------------------------------------------- helpers

55+ def say(msg):

56+ print(f"\n{'=' _72}\n=== {msg}\n{'=' <!---->_<!---->72}", flush=True)

57+

58+

59+ def sh(cmd, env=None, cwd=None, check=True):

60+ """Run a shell command and stream its output as it is produced."""

61+ print(f"$ {cmd}", flush=True)

62+ proc = subprocess.Popen(cmd, shell=True, cwd=cwd, env=env, text=True,

63+ stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

64+ tail = []

65+ for line in proc.stdout:

66+ print(line, end="", flush=True)

67+ tail.append(line)

68+ tail = tail[-30:]

69+ rc = proc.wait()

70+ if check and rc != 0:

71+ raise RuntimeError(f"command failed ({rc}): {cmd}")

72+ return rc

73+

74+

75+ def bg(cmd, logfile, env=None, cwd=None):

76+ """Start a long-lived process detached from this kernel call."""

77+ LOGS.mkdir(parents=True, exist_ok=True)

78+ log = open(logfile, "ab")

79+ return subprocess.Popen(cmd, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,

80+ stdin=subprocess.DEVNULL, start_new_session=True)

81+

82+

83+ def http_ok(url, timeout=3):

84+ try:

85+ req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (colab-demo2)"})

86+ with urllib.request.urlopen(req, timeout=timeout) as r:

87+ return 200 <= r.status < 400

88+ except Exception:

89+ return False

90+

91+

92+ def wait_for(url, seconds, label):

93+ end = time.time() + seconds

94+ while time.time() < end:

95+ if http_ok(url):

96+ return True

97+ time.sleep(2)

98+ print(f"[warn] {label} did not become ready within {seconds}s", flush=True)

99+ return False

100+

101+

102+ def tail_log(path, n=40):

103+ try:

104+ lines = Path(path).read_text(errors="replace").splitlines()[-n:]

105+ print(f"----- last {len(lines)} lines of {path} -----")

106+ print("\n".join(lines))

107+ except OSError:

108+ print(f"[warn] no log at {path}")

109+

110+

111+ def read_cfg():

112+ """Settings from /content/.env (uploaded colab.env). File values beat the kernel's env."""

113+ cfg = {}

114+ path = Path("/content/.env")

115+ if [path.is](http://path.is)\_file():

116+ for raw in [path.read](http://path.read)\_text().splitlines():

117+ line = raw\.strip()

118+ if line and not line.startswith("#") and "=" in line:

119+ k, \_, v = line.partition("=")

120+ cfg[k.strip()] = v.strip().strip('"').strip("'")

121+ return lambda key, default="": cfg.get(key) or os.environ.get(key) or default

122+

123+

124+ def pkill(pattern):

125+ [subprocess.run](http://subprocess.run)(["pkill", "-f", pattern], check=False)

126+

127+

128+ def stop_services(include_tunnel=True):

129+ for pat in ("uvicorn api_server:app", "next start", "next dev", "next-server"):

130+ pkill(pat)

131+ if include_tunnel:

132+ pkill("cloudflared tunnel")

133+ time.sleep(1)

134+

135+

136+ # ------------------------------------------------------------------------------------------- stages

137+ def stage_unpack():

138+ say("1. Unpack code bundle")

139+ if not [BUNDLE.is](http://BUNDLE.is)\_file():

140+ raise RuntimeError(f"{BUNDLE} missing -- run this via [launch.py](http://launch.py) (it uploads the bundle first)")

141+ ROOT.mkdir(parents=True, exist_ok=True)

142+ with zipfile.ZipFile(BUNDLE) as zf:

143+ zf.extractall(ROOT)

144+ for need in (DEMO2 / "api\_[server.py](http://server.py)", APP / "package.json", AGENT / "assistant/[graph.py](http://graph.py)"):

145+ if not [need.is](http://need.is)\_file():

146+ raise RuntimeError(f"bundle is incomplete, missing {need}")

147+ print(f"unpacked to {ROOT}")

148+

149+

150+ def stage_tts():

151+ say("2. TTS voice checkpoints")

152+ parts = sorted(TTS_PARTS.glob("[tts.zip](http://tts.zip).part\*"))

153+ if parts and not all((TTS_CACHE / v / "best_model.pth").is_file() for v in VOICES):

154+ zpath = Path("/content/tts\_[models.zip](http://models.zip)")

155+ with open(zpath, "wb") as out:

156+ for p in parts:

157+ with open(p, "rb") as src:

158+ shutil.copyfileobj(src, out, 16 _1024 <!---->_<!---->1024)

159+ TTS_CACHE.mkdir(parents=True, exist_ok=True)

160+ with zipfile.ZipFile(zpath) as zf:

161+ zf.extractall(TTS_CACHE)

162+ zpath.unlink()

163+ for p in parts:

164+ p.unlink()

165+ print("assembled checkpoints from uploaded parts")

166+ linked = 0

167+ for v in VOICES:

168+ src = TTS_CACHE / v / "best_model.pth"

169+ dst = TTS_DIR / v / "best_model.pth"

170+ if [src.is](http://src.is)\_file():

171+ dst.parent.mkdir(parents=True, exist_ok=True)

172+ if [dst.is](http://dst.is)\_symlink() or dst.exists():

173+ dst.unlink()

174+ dst.symlink_to(src)

175+ linked += 1

176+ if linked == len(VOICES):

177+ print("both voices linked")

178+ else:

179+ print("[warn] TTS checkpoints not found -> spoken answers will fail; text answers still work. "

180+ "Re-run [launch.py](http://launch.py) without --no-tts.")

181+

182+

183+ def stage_python():

184+ say("3. Python 3.11 environment (uv)")

185+ mark = VENV / ".deps_ok"

186+ if [PY.is](http://PY.is)\_file() and [mark.is](http://mark.is)\_file() and [mark.read](http://mark.read)\_text() == DEPS_VERSION:

187+ print("venv up to date")

188+ else:

189+ sh(f"{sys.executable} -m pip -q install uv")

190+ uv = f"{sys.executable} -m uv"

191+ sh(f"{uv} venv --python 3.11 --clear {VENV}")

192+ cons = Path("/content/constraints.txt")

193+ cons.write_text("\n".join(CONSTRAINTS) + "\n")

194+ pip = f"{uv} pip install --python {PY} -c {cons}"

195+ quote = lambda items: " ".join(f"'{i}'" for i in items)

196+ sh(f"{pip} {quote(PKG_TORCH)}")

197+ sh(f"{pip} {quote(PKG_TTS)}")

198+ sh(f"{pip} {quote(PKG_DEMO2)}")

199+ req = AGENT / "requirements.txt"

200+ if [req.is](http://req.is)\_file():

201+ sh(f"{pip} -r {req}")

202+ mark.write_text(DEPS_VERSION)

203+ sh(f"{PY} -c \\"import torch,fastapi,uvicorn,multipart,TTS,transformers,faster_whisper,chromadb,"

204+ f"langgraph,sentence_transformers,soundfile,edge_tts; "

205+ f"print('torch', torch.\__version\_\_, 'cuda', [torch.cuda.is](http://torch.cuda.is)\_available())\\"", env=clean_env())

206+

207+

208+ def clean_env(extra=None):

209+ """Environment for child processes: the kernel's own Python vars must not leak into the venv."""

210+ env = dict(os.environ)

211+ for k in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "NODE_ENV"):

212+ env.pop(k, None)

213+ env["PATH"] = f"{VENV / 'bin'}:{env.get('PATH', '')}"

214+ env["PYTHONUNBUFFERED"] = "1"

215+ env.update(extra or {})

216+ return env

217+

218+

219+ def backend_env(get):

220+ # CTranslate2 (faster-whisper) needs cuBLAS/cuDNN 12; torch's pip wheels ship them inside site-packages.

221+ libs = sorted(str(p) for p in VENV.glob("lib/python3.11/site-packages/nvidia/\*/lib"))

222+ ld = ":".join(libs + [os.environ.get("LD_LIBRARY_PATH", "")]).strip(":")

223+ env = clean_env({

224+ "LLM_PROVIDER": "ollama",

225+ "OLLAMA_BASE_URL": OLLAMA_URL,

226+ "OLLAMA_MODEL": get("MODEL_TAG", "qwen3.5:9b"),

227+ "OLLAMA_NUM_CTX": get("OLLAMA_NUM_CTX", "16384"),

228+ "OLLAMA_KEEP_ALIVE": "-1",

229+ "DEMO2_CODE_ROOT": str(ROOT / "code"),

230+ "DEMO2_STT_DEVICE": get("DEMO2_STT_DEVICE", "auto"),

231+ "DEMO2_TTS_DEVICE": get("DEMO2_TTS_DEVICE", "cpu"),

232+ "DEMO2_WHISPER_MODEL": get("DEMO2_WHISPER_MODEL", "small"),

233+ "DEMO2_SPEECH_THREADS": "8",

234+ "JEV_ROUTING_MODE": "off",

235+ "USE_TF": "0", "USE_FLAX": "0", "USE_JAX": "0", "USE_TORCH": "1",

236+ "TOKENIZERS_PARALLELISM": "false",

237+ "LD_LIBRARY_PATH": ld,

238+ })

239+ if get("GROQ_API_KEY"):

240+ env["GROQ_API_KEY"] = get("GROQ_API_KEY")

241+ return env

242+

243+

244+ def stage_ollama(get):

245+ say("4. Ollama (GPU) + model")

246+ model = get("MODEL_TAG", "qwen3.5:9b")

247+ if not shutil.which("ollama"):

248+ sh("command -v zstd >/dev/null 2>&1 || (apt-get -qq update && apt-get -qq install -y zstd)", check=False)

249+ sh("curl -fsSL https://ollama.com/install.sh | sh")

250+ if not http_ok(f"{OLLAMA_URL}/api/version"):

251+ env = dict(os.environ, OLLAMA_HOST="127.0.0.1:11434", OLLAMA_KEEP_ALIVE="-1")

252+ bg(["ollama", "serve"], LOGS / "ollama.log", env=env)

253+ if not wait_for(f"{OLLAMA_URL}/api/version", 60, "ollama"):

254+ tail_log(LOGS / "ollama.log")

255+ raise RuntimeError("ollama did not start")

256+ listed = [subprocess.run](http://subprocess.run)(["ollama", "list"], text=True, capture_output=True).stdout

257+ if model not in listed:

258+ sh(f"ollama pull {model}")

259+ # Load the model onto the GPU now, with the same context the agent will request (avoids a reload on turn 1).

260+ body = json.dumps({"model": model, "prompt": "ok", "stream": False, "keep_alive": -1,

261+ "options": {"num_predict": 1, "num_ctx": int(get("OLLAMA_NUM_CTX", "16384"))}}).encode()

262+ req = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=body,

263+ headers={"Content-Type": "application/json"})

264+ try:

265+ urllib.request.urlopen(req, timeout=300).read()

266+ except Exception as exc:

267+ print(f"[warn] model warm-up failed: {exc}")

268+ sh("ollama ps", check=False)

269+

270+ env = backend_env(get)

271+ # The agent needs a local tokenizer file for its prompt budgeting.

272+ sh(f"{PY} setup\_[local.py](http://local.py)", env=env, cwd=AGENT, check=False)

273+ # Pre-fetch the Whisper model so the first microphone question is not delayed by a download.

274+ sh(f"{PY} -c \\"from faster_whisper import download_model; "

275+ f"print(download_model('{get('DEMO2_WHISPER_MODEL', 'small')}'))\\"", env=env, check=False)

276+

277+

278+ def stage_backend(get):

279+ say("5. Demo 2 FastAPI backend")

280+ port = get("API_PORT", "8020")

281+ pkill("uvicorn api_server:app")

282+ time.sleep(1)

283+ (DEMO2 / "data").mkdir(exist_ok=True)

284+ bg([str(PY), "-m", "uvicorn", "api_server:app", "--host", "127.0.0.1", "--port", port],

285+ LOGS / "backend.log", env=backend_env(get), cwd=DEMO2)

286+ if not wait_for(f"http://127.0.0.1:{port}/api/health", 240, "backend"):

287+ tail_log(LOGS / "backend.log", 80)

288+ raise RuntimeError("Demo 2 backend did not come up")

289+ print(f"backend healthy on :{port}")

290+

291+

292+ def node_version_ok():

293+ if not shutil.which("node"):

294+ return False

295+ out = [subprocess.run](http://subprocess.run)(["node", "--version"], text=True, capture_output=True).stdout.strip()

296+ m = re.match(r"v(\d+)\\.(\d+)", out)

297+ return bool(m) and (int([m.group](http://m.group)(1)), int([m.group](http://m.group)(2))) >= (20, 9)

298+

299+

300+ def stage_web(get):

301+ say("6. Next.js web app")

302+ if not node_version_ok():

303+ print("installing Node.js 22")

304+ sh("curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y -qq nodejs")

305+ sh("node --version && npm --version")

306+ web, api = get("WEB_PORT", "3001"), get("API_PORT", "8020")

307+ env = backend_env(get)

308+ env.update({"DEMO2_API_URL": f"http://127.0.0.1:{api}", "DEMO2_DIR": str(DEMO2), "DEMO2_PYTHON": str(PY),

309+ "NEXT_TELEMETRY_DISABLED": "1", "HOSTNAME": "127.0.0.1", "PORT": web})

310+ if not (APP / "node_modules/.bin/next").is_file():

311+ sh("npm ci --no-audit --no-fund", cwd=APP, env=env)

312+ shutil.rmtree(APP / ".next", ignore_errors=True)

313+ built = sh("npm run build", cwd=APP, env=env, check=False) == 0

314+ mode = "start" if built else "dev"

315+ if not built:

316+ print("[warn] production build failed -> falling back to `next dev` (slower first page loads)")

317+ bg([str(APP / "node_modules/.bin/next"), mode, "-H", "127.0.0.1", "-p", web],

318+ LOGS / "web.log", env=env, cwd=APP)

319+ if not wait_for(f"http://127.0.0.1:{web}/api/py/health", 180, "web app"):

320+ tail_log(LOGS / "web.log", 60)

321+ raise RuntimeError("web app did not come up")

322+ print(f"web app ready on :{web} ({mode})")

323+

324+

325+ def stage_tunnel(get):

326+ say("7. Public HTTPS tunnel (Cloudflare quick tunnel)")

327+ web = get("WEB_PORT", "3001")

328+ url_file = LOGS / "public_url.txt"

329+ pkill("cloudflared tunnel")

330+ time.sleep(1)

331+ if not shutil.which("cloudflared"):

332+ sh("curl -fsSL -o /usr/local/bin/cloudflared "

333+ "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 "

334+ "&& chmod +x /usr/local/bin/cloudflared")

335+ logfile = LOGS / "cloudflared.log"

336+ logfile.write_bytes(b"")

337+ bg(["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{web}", "--no-autoupdate"], logfile)

338+ url = None

339+ for \_ in range(60):

340+ m = [re.search](http://re.search)(r"https://[-a-z0-9]+\.trycloudflare\.com", [logfile.read](http://logfile.read)\_text(errors="replace"))

341+ if m:

342+ url = [m.group](http://m.group)(0)

343+ break

344+ time.sleep(1)

345+ if not url:

346+ tail_log(logfile)

347+ raise RuntimeError("could not obtain a tunnel URL")

348+ ok = wait_for(f"{url}/api/py/health", 90, "public tunnel")

349+ url_file.write_text(url + "\n")

350+ return url, ok

351+

352+

353+ # ----------------------------------------------------------------------------------------------- main

354+ def main():

355+ action = os.environ.pop("ACTION", "run")

356+ LOGS.mkdir(parents=True, exist_ok=True)

357+ if action == "stop":

358+ stop_services()

359+ print("services stopped (Ollama left running; stop the Colab session to release the GPU)")

360+ return

361+ t0 = time.time()

362+ get = read_cfg()

363+ say("0. GPU")

364+ sh("nvidia-smi --query-gpu=name,[memory.total](http://memory.total),[memory.free](http://memory.free) --format=csv "

365+ "|| echo 'WARNING: no GPU visible'", check=False)

366+ try:

367+ stop_services(include_tunnel=False) # free ports before the code on disk changes

368+ stage_unpack()

369+ stage_tts()

370+ stage_python()

371+ stage_ollama(get)

372+ stage_backend(get)

373+ stage_web(get)

374+ url, ok = stage_tunnel(get)

375+ except Exception as exc:

376+ say(f"FAILED: {exc}")

377+ print(f"Logs are in {LOGS}/ (backend.log, web.log, ollama.log, cloudflared.log).")

378+ sys.exit(1)

379+

380+ say(f"READY in {time.time() - t0:.0f}s")

381+ print(f"\n OPEN: {url}\n")

382+ if not ok:

383+ print("(The tunnel answered no health check yet -- DNS can take up to a minute; just retry the URL.)")

384+ print("Notes:")

385+ print(" - The URL is public and has NO login. Anyone who has it can use the helpdesk and your GPU.")

386+ print(" - First question is slower (embedding model + graph load); Chhattisgarhi (MMS-1B) downloads ~4 GB on first

use.")

387+ print(" - The URL changes whenever the tunnel restarts. Stop with: python3 run_colab/[launch.py](http://launch.py) --stop")

388+

389+

390+ if **name** == "\__main\_\_":

391+ main()

▸ Credits: 8.22 • Time: 4m 10s

● The monthly usage limit has been reached (request_id: 51fd7283-2045-4b9d-bf20-0e536e78ba62)
