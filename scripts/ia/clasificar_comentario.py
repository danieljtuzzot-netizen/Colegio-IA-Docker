"""Pipeline local experimental: informatividad -> BETO, sin borrar comentarios."""
import argparse
import json
from pathlib import Path
import re
from informatividad_comun import ROOT,cargar_filtro,predecir_filtro,normalizar,sha,percent
from piloto_beto import setup,LABELS

FILTRO_DEFAULT='informatividad_cpu_20261112_v1'
BETO_DEFAULT='sentimiento_cpu_20261112_v1'

class ClasificadorComentarios:
    def __init__(self,filtro=FILTRO_DEFAULT,beto=BETO_DEFAULT):
        if not all(re.fullmatch(r'[A-Za-z0-9_-]{1,64}',n) for n in (filtro,beto)):
            raise ValueError('Versión inválida')
        setup(True)
        self.filtro_id,self.beto_id=filtro,beto
        self.filter_folder=ROOT/'data/ia/entrenamientos'/filtro
        self.filter,self.config,self.filter_manifest=cargar_filtro(self.filter_folder)
        self.beto_folder=ROOT/'data/ia/entrenamientos'/beto
        self.beto_state=json.loads((self.beto_folder/'estado.json').read_text(encoding='utf-8'))
        assert self.beto_state['estado']=='COMPLETADO' and not self.beto_state['smoke']
        assert self.beto_state['dataset']==self.config['dataset_version']
        assert self.beto_state['label2id']==LABELS
        self._beto=None;self._tokenizer=None

    def _load_beto(self):
        if self._beto is not None:return
        import torch
        from transformers import AutoTokenizer,AutoModelForSequenceClassification
        folder=(self.beto_folder/self.beto_state['mejor_checkpoint']).resolve()
        assert folder.is_relative_to(self.beto_folder.resolve()),'Ruta de checkpoint fuera de ejecución'
        for name,expected in self.beto_state['hashes_mejor_checkpoint'].items():
            assert Path(name).name==name and sha(folder/name)==expected,'Checkpoint alterado'
        torch.set_num_threads(4)
        self._tokenizer=AutoTokenizer.from_pretrained(str(folder),local_files_only=True,trust_remote_code=False)
        self._beto=AutoModelForSequenceClassification.from_pretrained(str(folder),local_files_only=True,trust_remote_code=False,use_safetensors=True).to('cpu').eval()

    def clasificar_lote(self,questions,comments,confirmaciones=None,referencia_revision=None):
        if len(questions)!=len(comments):raise ValueError('Cantidad de preguntas y comentarios distinta')
        if not questions:return []
        confirmaciones=confirmaciones if confirmaciones is not None else [None]*len(questions)
        if len(confirmaciones)!=len(questions) or any(c not in (None,'INFORMATIVO','NO_INFORMATIVO') for c in confirmaciones):
            raise ValueError('Confirmaciones inválidas')
        if any(c is not None for c in confirmaciones) and not (referencia_revision and re.fullmatch(r'[A-Za-z0-9_-]{1,64}',referencia_revision)):
            raise ValueError('La confirmación requiere una referencia técnica de revisión')
        for q,c in zip(questions,comments):
            if not normalizar(q):raise ValueError('La pregunta es obligatoria para interpretar el contexto')
            normalizar(c)
        binary=predecir_filtro(self.filter,self.config,questions,comments)
        result=[];pending=[]
        for index,decision in enumerate(binary):
            confirmed=confirmaciones[index]
            label=confirmed or decision['etiqueta']
            if confirmed=='INFORMATIVO' and not normalizar(comments[index]):
                raise ValueError('Un comentario vacío no puede confirmarse INFORMATIVO')
            informative=label=='INFORMATIVO'
            action='PASA_A_SENTIMIENTO' if informative else 'NO_INFORMATIVO_CONFIRMADO_SIN_BORRAR' if confirmed else 'RETENIDO_PARA_REVISION_SIN_BORRAR'
            result.append({'estado':'EXPERIMENTAL','informatividad':label,'sentimiento':None,'informatividad_detalle':decision,'revision_operador':{'etiqueta':confirmed,'referencia':referencia_revision,'origen':'DECLARADA_POR_OPERADOR'} if confirmed else None,'sentimiento_detalle':None,'requiere_revision_humana':not informative and confirmed is None,'accion':action,'beto_ejecutado':False,'versiones':{'pipeline':'comentarios_v1','filtro':self.filtro_id,'reglas':self.config['reglas_version'],'beto':self.beto_id,'mejor_epoca_beto':self.beto_state['mejor_epoca']}})
            if informative:pending.append(index)
        if pending:
            self._load_beto()
            import torch
            maximum=self.beto_state['config']['max_length']
            for start in range(0,len(pending),8):
                indices=pending[start:start+8]
                qs=[questions[i] for i in indices];cs=[comments[i] for i in indices]
                q_lengths=[len(x) for x in self._tokenizer(qs,add_special_tokens=False)['input_ids']]
                if any(n+3>=maximum for n in q_lengths):
                    raise ValueError('Pregunta demasiado larga para conservarla en el modelo')
                full=self._tokenizer(qs,cs,truncation=False,verbose=False)['input_ids']
                encoded=self._tokenizer(qs,cs,truncation='only_second',max_length=maximum,padding=True,return_tensors='pt')
                with torch.no_grad():scores=torch.softmax(self._beto(**encoded).logits,dim=-1)
                assert torch.isfinite(scores).all()
                for index,probs,tokens in zip(indices,scores,full):
                    label=next(k for k,v in LABELS.items() if v==int(probs.argmax()))
                    result[index].update({'sentimiento':label,'beto_ejecutado':True,'sentimiento_detalle':{'etiqueta':label,'score_visible':percent(float(probs[LABELS[label]])),'scores_raw_no_calibrados':{k:float(probs[v]) for k,v in LABELS.items()},'comentario_truncado_para_modelo':len(tokens)>maximum}})
        return result

    def clasificar(self,question,comment,confirmada=None,referencia_revision=None):
        return self.clasificar_lote([question],[comment],[confirmada],referencia_revision)[0]

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pregunta',required=True)
    parser.add_argument('--comentario',required=True)
    parser.add_argument('--filtro',default=FILTRO_DEFAULT)
    parser.add_argument('--beto',default=BETO_DEFAULT)
    parser.add_argument('--informatividad-confirmada',choices=['INFORMATIVO','NO_INFORMATIVO'])
    parser.add_argument('--referencia-revision')
    args=parser.parse_args()
    pipeline=ClasificadorComentarios(args.filtro,args.beto)
    print(json.dumps(pipeline.clasificar(args.pregunta,args.comentario,args.informatividad_confirmada,args.referencia_revision),ensure_ascii=True))
