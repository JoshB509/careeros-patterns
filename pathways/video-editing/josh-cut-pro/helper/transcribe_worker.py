"""Runs Whisper in its own process, so a crash here can never take the helper down.

python transcribe_worker.py <mic.f32> <out.json> <model dir> <device> <compute type> <threads> <batched 0/1> <beam>
Writes <out.json>.progress as it goes and <out.json> when done. Exit code 0 means success.
"""
import json, os, sys

os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')
os.environ['HF_HUB_OFFLINE'] = '1'


def main():
    mic_path, out_path, model_dir, device, ctype, threads, batched, beam = sys.argv[1:9]
    import numpy as np
    from faster_whisper import WhisperModel
    audio = np.fromfile(mic_path, dtype='<f4')
    total = max(1.0, len(audio) / 16000.0)
    model = WhisperModel(model_dir, device=device, compute_type=ctype, cpu_threads=int(threads), local_files_only=True)
    opts = dict(language='en', word_timestamps=True, vad_filter=True, beam_size=int(beam))
    if batched == '1':
        from faster_whisper import BatchedInferencePipeline
        segments, _ = BatchedInferencePipeline(model=model).transcribe(audio, batch_size=16 if device == 'cuda' else 8, **opts)
    else:
        segments, _ = model.transcribe(audio, condition_on_previous_text=False, **opts)
    out = []
    progress = out_path + '.progress'
    for seg in segments:
        out.append(dict(start=seg.start, end=seg.end, text=seg.text,
                        words=[dict(start=w.start, end=w.end, word=w.word, probability=w.probability) for w in (seg.words or [])]))
        with open(progress, 'w') as f:
            f.write(str(min(99, int(100 * seg.end / total))))
    out.sort(key=lambda s: s['start'])
    tmp = out_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(out, f)
    os.replace(tmp, out_path)


if __name__ == '__main__':
    main()
