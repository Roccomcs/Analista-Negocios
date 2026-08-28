"""Interfaz de escritorio pequeña. El trabajo se ejecuta en un proceso separado."""
import os
import queue
import subprocess
import sys
import threading
from uuid import uuid4
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from .providers import ZONES,CATEGORIES
from .settings import ROOT,load_settings


class App:
    def __init__(self,root):
        self.root=root
        root.title('Cadmo · Analista de negocios')
        root.geometry('980x730')
        root.minsize(800,650)
        self.running=False
        self.messages=queue.Queue()
        self.csv=tk.StringVar()
        self.zone=tk.StringVar(value='Villa Urquiza')
        self.category=tk.StringVar(value='todos')
        self.limit=tk.StringVar(value='50')
        self.stop_file=None
        self.refresh=tk.BooleanVar(value=False)
        frame=ttk.Frame(root,padding=24);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='CADMO / Analista de negocios',font=('Segoe UI',21,'bold')).pack(anchor='w')
        ttk.Label(frame,text='Encontrar negocios con contacto · Sin IA · Guardar un Excel simple',font=('Segoe UI',11)).pack(anchor='w',pady=(5,14))
        ttk.Label(frame,text='Fuente automática: OpenStreetMap. Cobertura parcial; no es una lista completa de Google Maps.',wraplength=890).pack(anchor='w')
        ttk.Label(frame,text='No se envían mensajes. Guardá y cerrá el Excel antes de ejecutar.',foreground='#8B5800').pack(anchor='w',pady=(2,14))
        fields=ttk.Frame(frame);fields.pack(fill='x')
        for i,(label,var,values) in enumerate([('Barrio',self.zone,ZONES),('Rubro',self.category,list(CATEGORIES)),('Propuestas nuevas',self.limit,None)]):
            ttk.Label(fields,text=label).grid(row=0,column=i,sticky='w',padx=(0,18))
            control=ttk.Combobox(fields,textvariable=var,values=values,state='readonly',width=27) if values else ttk.Spinbox(fields,textvariable=var,from_=1,to=200,width=10)
            control.grid(row=1,column=i,sticky='w',padx=(0,18),pady=(4,10))
        options=ttk.Frame(frame);options.pack(fill='x',pady=5)
        ttk.Checkbutton(options,text='Volver a revisar los anteriores (no cuentan como propuestas nuevas)',variable=self.refresh).pack(side='left')
        ttk.Label(frame,text='Una propuesta = un negocio con Instagram, WhatsApp, correo o teléfono. Si la zona no alcanza, se informa el faltante.',wraplength=890).pack(anchor='w',pady=5)
        imports=ttk.Frame(frame);imports.pack(fill='x',pady=8)
        ttk.Button(imports,text='Elegir CSV propio…',command=self.choose_csv).pack(side='left')
        ttk.Button(imports,text='Usar OpenStreetMap',command=lambda:self.csv.set('')).pack(side='left',padx=8)
        ttk.Label(imports,textvariable=self.csv,wraplength=550).pack(side='left')
        buttons=ttk.Frame(frame);buttons.pack(fill='x',pady=(5,12))
        self.run_button=ttk.Button(buttons,text='Buscar propuestas',command=self.start);self.run_button.pack(side='left')
        self.stop_button=ttk.Button(buttons,text='Detener y guardar',command=self.stop,state='disabled');self.stop_button.pack(side='left',padx=6)
        ttk.Button(buttons,text='Exportar / sincronizar Excel',command=lambda:self.execute(['exportar'])).pack(side='left',padx=8)
        ttk.Button(buttons,text='Diagnóstico',command=lambda:self.execute(['diagnostico'])).pack(side='left')
        ttk.Button(frame,text='Abrir Excel',command=self.open_output).pack(anchor='w')
        self.status=tk.StringVar(value='Listo. Elegí la zona y la meta de propuestas nuevas.')
        ttk.Label(frame,textvariable=self.status,font=('Segoe UI',10,'bold')).pack(anchor='w',pady=4)
        self.text=tk.Text(frame,height=16,wrap='word',font=('Consolas',10),background='#16191F',foreground='#EEECE7',padx=12,pady=12)
        self.text.pack(fill='both',expand=True)
        self.text.configure(state='disabled')
        ttk.Label(frame,text='Comprobá que el contacto corresponda al negocio. No se envían mensajes ni se asume permiso para publicidad.',wraplength=890).pack(anchor='w',pady=(10,0))
        root.after(100,self.poll)
        root.protocol('WM_DELETE_WINDOW',self.close)

    def choose_csv(self):
        chosen=filedialog.askopenfilename(filetypes=[('CSV','*.csv')])
        if chosen:self.csv.set(chosen)

    def open_output(self):
        settings=load_settings()
        book=settings.path(settings.output)
        book.parent.mkdir(parents=True,exist_ok=True)
        os.startfile(book if book.exists() else book.parent)

    def start(self):
        try:
            count=int(self.limit.get())
            if not 1<=count<=200:raise ValueError()
        except ValueError:
            messagebox.showerror('Propuestas','Elegí una meta entre 1 y 200 propuestas nuevas.');return
        args=['ejecutar','--zona',self.zone.get(),'--rubro',self.category.get(),'--cantidad',str(count)]
        if self.csv.get():args+=['--csv',self.csv.get()]
        if self.refresh.get():args+=['--actualizar']
        self.execute(args)

    def stop(self):
        if self.running and self.stop_file:
            self.stop_file.touch()
            self.stop_button.configure(state='disabled')
            self.status.set('Deteniendo al terminar el negocio actual; se guardará el Excel…')

    def execute(self,args):
        if self.running:
            messagebox.showinfo('En curso','Esperá a que termine la ejecución actual.');return
        if args[0]=='ejecutar':
            self.stop_file=ROOT/'data'/'tmp'/('stop-'+str(uuid4()))
            self.stop_file.parent.mkdir(parents=True,exist_ok=True)
            args=[*args,'--detener-archivo',str(self.stop_file)]
            self.stop_button.configure(state='normal')
        self.running=True;self.run_button.configure(state='disabled');self.status.set('Buscando… el progreso aparece abajo.')
        threading.Thread(target=self.worker,args=(args,),daemon=True).start()

    def worker(self,args):
        try:
            flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            exe=str(ROOT/'.venv'/'Scripts'/'python.exe') if os.name=='nt' else sys.executable
            with subprocess.Popen([exe,'-u','-m','analista.cli',*args],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',creationflags=flags) as process:
                for line in process.stdout:self.messages.put(('log',line))
                code=process.wait()
            self.messages.put(('done',code))
        except Exception as exc:
            self.messages.put(('log',str(exc)+'\n'));self.messages.put(('done',1))

    def poll(self):
        while not self.messages.empty():
            kind,value=self.messages.get_nowait()
            if kind=='log':
                self.text.configure(state='normal');self.text.insert('end',value);self.text.see('end');self.text.configure(state='disabled')
            else:
                self.running=False;self.run_button.configure(state='normal')
                self.stop_button.configure(state='disabled')
                if self.stop_file:
                    self.stop_file.unlink(missing_ok=True);self.stop_file=None
                self.status.set('Finalizado.' if value==0 else 'Excel guardado con resultados parciales; revisá el detalle.' if value==3 else 'Finalizó con avisos o errores. Revisá el registro.')
        self.root.after(150,self.poll)

    def close(self):
        if self.running:
            messagebox.showinfo('Trabajo en curso','Esperá a que termine para cerrar sin interrumpir el guardado.');return
        self.root.destroy()


def main():
    root=tk.Tk();App(root);root.mainloop()


if __name__=='__main__':main()
