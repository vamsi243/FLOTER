"""Local OmniParser model adapter, separate from FLOTER's Qt/voice runtime.

Uses Microsoft's YOLOv9-E region detector and Florence-2 icon-caption weights,
with EasyOCR labels. No screen capture or desktop execution is exposed here.
"""
import argparse
import base64
import io
import json
import secrets
import sys
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

def main():
    os.environ.setdefault('OMP_NUM_THREADS','2')
    os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
    parser=argparse.ArgumentParser()
    root=Path(__file__).resolve().parents[1]
    parser.add_argument('--repo',type=Path,default=root/'.tools/OmniParser')
    parser.add_argument('--weights',type=Path,default=root/'models/omniparser')
    parser.add_argument('--device',choices=['cuda','cpu'],default='cuda')
    parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--token-file',type=Path,default=Path.home()/'.floter/omniparser.token')
    parser.add_argument('--check-image',type=Path)
    args=parser.parse_args()
    import torch
    torch.set_num_threads(2)
    import numpy as np
    from PIL import Image
    import easyocr
    from transformers import AutoProcessor, AutoModelForCausalLM
    if args.device=='cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA was requested but is unavailable in this runtime')
    sys.path.insert(0,str(args.repo.resolve()))
    from util.yolov9 import YOLOv9Detector
    detector=YOLOv9Detector(args.weights/'icon_detect_v3/model.pt',device=args.device)
    if args.device=='cuda': detector.model.half()
    caption_dir=args.weights/'icon_caption'
    processor=AutoProcessor.from_pretrained(args.weights/'processor',trust_remote_code=True,local_files_only=True)
    caption=AutoModelForCausalLM.from_pretrained(caption_dir,trust_remote_code=True,local_files_only=True,
        torch_dtype=torch.float16 if args.device=='cuda' else torch.float32,attn_implementation='eager').to(args.device).eval()
    # OCR stays on CPU so CUDA memory is available for detection, captions and Whisper.
    ocr=easyocr.Reader(['en'],gpu=False,model_storage_directory=str(args.weights/'ocr'),download_enabled=False)

    @torch.inference_mode()
    def parse(image):
        image=image.convert('RGB'); w,h=image.size
        texts=[]
        for quad,label,score in ocr.readtext(np.asarray(image)):
            if score<.4: continue
            xs=[p[0] for p in quad]; ys=[p[1] for p in quad]
            texts.append({'bbox':[float(min(xs)/w),float(min(ys)/h),float(max(xs)/w),float(max(ys)/h)],'content':label})
        prediction=detector.predict(source=image,conf=.05,imgsz=640,iou=.5)[0]
        icons=[]
        for raw in prediction.boxes.xyxy.cpu().tolist()[:160]:
            x1,y1,x2,y2=raw
            if x2-x1<3 or y2-y1<3: continue
            box=[max(0,x1/w),max(0,y1/h),min(1,x2/w),min(1,y2/h)]
            label=' '.join(t['content'] for t in texts if box[0]<=(t['bbox'][0]+t['bbox'][2])/2<=box[2] and box[1]<=(t['bbox'][1]+t['bbox'][3])/2<=box[3])
            icons.append({'bbox':box,'content':label,'crop':image.crop((x1,y1,x2,y2))})
        unlabeled=[i for i in icons if not i['content']]
        for start in range(0,len(unlabeled),1):
            batch=unlabeled[start:start+1]
            inputs=processor(text=['<CAPTION>']*len(batch),images=[i['crop'] for i in batch],return_tensors='pt').to(args.device)
            if args.device=='cuda': inputs['pixel_values']=inputs['pixel_values'].half()
            output=caption.generate(input_ids=inputs['input_ids'],pixel_values=inputs['pixel_values'],max_new_tokens=24,num_beams=1,do_sample=False)
            for entry,label in zip(batch,processor.batch_decode(output,skip_special_tokens=True)):
                entry['content']=label
        return {'device':args.device,'gpu':torch.cuda.get_device_name(0) if args.device=='cuda' else None,
            'elements':texts+[{'bbox':i['bbox'],'content':i['content']} for i in icons]}

    if args.check_image:
        import time
        started=time.monotonic()
        result=parse(Image.open(args.check_image))
        print(json.dumps({'device':result['device'],'gpu':result['gpu'],'elements':len(result['elements']),'seconds':round(time.monotonic()-started,2)}))
        return
    token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            if self.path!='/parse' or not secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):
                self.send_error(403); return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<16_000_000: raise ValueError('Invalid request size')
                body=json.loads(self.rfile.read(size))
                image=Image.open(io.BytesIO(base64.b64decode(body['image'],validate=True)))
                if image.width*image.height>20_000_000: raise ValueError('Image too large')
                payload=json.dumps(parse(image)).encode()
                self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(payload))); self.end_headers(); self.wfile.write(payload)
            except Exception:
                self.send_error(500,'OmniParser failed; inspect runtime configuration or GPU memory')
    server=HTTPServer(('127.0.0.1',args.port),Handler)
    args.token_file.parent.mkdir(parents=True,exist_ok=True)
    args.token_file.write_text(token)
    print('OmniParser ready on loopback; device='+args.device,flush=True)
    server.serve_forever()

if __name__=='__main__': main()
