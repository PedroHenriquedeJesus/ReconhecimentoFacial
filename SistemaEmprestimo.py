import cv2
import os
import pandas as pd
import threading
import customtkinter as ctk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from datetime import datetime
from deepface import DeepFace
import time

# Configurações de aparência do CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AppEmprestimo(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Configurações da Janela Principal ---
        self.title("Sistema de Empréstimo com FaceID")
        self.state("zoomed") # Inicia a janela maximizada

        # --- Variáveis de Controle e Caminhos ---
        self.path_db = "base_rostos"      # Pasta com as fotos para reconhecimento
        self.planilha_nome = "emprestimos.xlsx"
        self.current_user = ""            # Armazena o usuário detectado no momento
        self.last_seen_time = time.time() # Timer para limpar o campo por inatividade

        # Controle de interface e edição
        self.show_overlay = False
        self.overlay_image = None
        self.overlay_timer = 0
        self.edit_mode_index = None       # Guarda o índice da linha quando estamos editando

        self.lista_itens = ["SELECIONE UM ITEM", "NOTEBOOK", "MOUSE", "TECLADO", "MONITOR", "FONTE", "OUTROS"]
        self.lista_status = ["PENDENTE", "DEVOLVIDO"]

        # Configuração de colunas da grade (grid)
        self.grid_columnconfigure(0, weight=1) # Coluna da Câmera
        self.grid_columnconfigure(1, weight=1) # Coluna do Formulário
        self.grid_rowconfigure(1, weight=1)    # Linha da Tabela

        # --- Interface: CÂMERA (Lado Esquerdo) ---
        self.video_label = ctk.CTkLabel(self, text="Iniciando...", font=("Arial", 20))
        self.video_label.grid(row=0, column=0, padx=20, pady=20)

        # --- Interface: FORMULÁRIO (Lado Direito) ---
        self.form_frame = ctk.CTkFrame(self)
        self.form_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

        ctk.CTkLabel(self.form_frame, text="DADOS DO REGISTRO", font=("Arial", 24, "bold"), text_color="#5dade2").pack(pady=15)

        # Campo de Usuário (Preenchido automaticamente pelo FaceID ou manual)
        self.entry_usuario = ctk.CTkEntry(self.form_frame, placeholder_text="Usuário...", width=350, height=40)
        self.entry_usuario.pack(pady=5)

        # Menu Suspenso de Itens
        self.combo_item = ctk.CTkComboBox(self.form_frame, values=self.lista_itens, command=self.gerenciar_campos_extras,
                                          width=350, height=40, state="readonly")
        self.combo_item.pack(pady=5)
        self.combo_item.set("SELECIONE UM ITEM")
        # Evento para abrir a lista ao clicar em qualquer lugar da caixa
        self.combo_item.bind("<Button-1>", lambda event: self.combo_item._canvas.after(10, self.combo_item._open_dropdown_menu))

        self.entry_qtd = ctk.CTkEntry(self.form_frame, placeholder_text="Quantidade", width=350, height=40)
        self.entry_qtd.pack(pady=5)

        # Campo Extra (Aparece apenas se for Notebook ou Outros)
        self.frame_extra = ctk.CTkFrame(self.form_frame, fg_color="transparent")
        self.label_extra = ctk.CTkLabel(self.frame_extra, text="", font=("Arial", 12), text_color="#a9cce3")
        self.label_extra.pack()
        self.entry_extra = ctk.CTkEntry(self.frame_extra, width=350, height=40)
        self.entry_extra.pack(pady=5)

        # Menu de Status (Visível apenas durante a Edição)
        self.frame_status_edit = ctk.CTkFrame(self.form_frame, fg_color="transparent")
        ctk.CTkLabel(self.frame_status_edit, text="Alterar Status:", font=("Arial", 12), text_color="#a9cce3").pack()
        self.combo_status = ctk.CTkComboBox(self.frame_status_edit, values=self.lista_status, width=350, height=40, state="readonly")
        self.combo_status.pack(pady=5)
        self.combo_status.bind("<Button-1>", lambda event: self.combo_status._canvas.after(10, self.combo_status._open_dropdown_menu))

        # Mensagens de feedback (Salvo, Erro, etc)
        self.lbl_status_msg = ctk.CTkLabel(self.form_frame, text="", font=("Arial", 14, "bold"))
        self.lbl_status_msg.pack(pady=5)

        self.btn_enviar = ctk.CTkButton(self.form_frame, text="REGISTRAR EMPRÉSTIMO", fg_color="#2874a6", hover_color="#1b4f72", width=350, height=50, command=self.salvar_dados)
        self.btn_enviar.pack(pady=5)

        self.btn_cancelar_edit = ctk.CTkButton(self.form_frame, text="CANCELAR EDIÇÃO", fg_color="#555555", width=350, height=30, command=self.limpar_campos)

        # --- Interface: TABELA (Parte Inferior) ---
        self.table_frame = ctk.CTkFrame(self)
        self.table_frame.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 20), sticky="nsew")
        self.setup_tabela()

        # Botões de Ação da Tabela
        self.btn_frame = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        self.btn_frame.pack(pady=10)

        self.btn_devolver = ctk.CTkButton(self.btn_frame, text="DAR BAIXA", fg_color="#3498db", hover_color="#2980b9", width=150, command=self.marcar_devolvido)
        self.btn_devolver.grid(row=0, column=0, padx=10)

        self.btn_editar = ctk.CTkButton(self.btn_frame, text="EDITAR", fg_color="#85c1e9", hover_color="#5dade2", text_color="#1b4f72", width=150, command=self.preparar_edicao)
        self.btn_editar.grid(row=0, column=1, padx=10)

        self.btn_excluir = ctk.CTkButton(self.btn_frame, text="EXCLUIR", fg_color="#dc3545", hover_color="#c0392b", width=150, command=self.excluir_registro)
        self.btn_excluir.grid(row=0, column=2, padx=10)

        # Iniciar Câmera e Lógica
        self.cap = cv2.VideoCapture(0)
        self.start_logic()
        self.atualizar_tabela()

    def setup_tabela(self):
        """Configura o visual e as colunas da tabela (Treeview)."""
        self.colunas = ("ID", "USUÁRIO", "ITEM", "Nº NOTEBOOK", "QTD", "DATA EMPRÉSTIMO", "STATUS", "DATA DEVOLUÇÃO")
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", rowheight=30, fieldbackground="#2b2b2b", borderwidth=0)
        style.configure("Treeview.Heading", background="#21618c", foreground="white", relief="flat")
        style.map("Treeview", background=[('selected', '#2e86c1')])

        self.tree = ttk.Treeview(self.table_frame, columns=self.colunas, show="headings")
        for col in self.colunas:
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor="center", width=120)

        # Cores para o texto dependendo do status
        self.tree.tag_configure("pendente", foreground="#FF6B6B")
        self.tree.tag_configure("devolvido", foreground="#aed6f1")
        self.tree.pack(expand=True, fill="both", padx=10, pady=5)

    def atualizar_tabela(self):
        """Lê a planilha Excel e atualiza os dados visíveis na tabela."""
        for i in self.tree.get_children(): self.tree.delete(i) # Limpa a tabela atual
        if os.path.exists(self.planilha_nome):
            df = pd.read_excel(self.planilha_nome).astype(str).replace("nan", "-")
            for index, row in df.iterrows():
                tag = "devolvido" if row["STATUS"].upper() == "DEVOLVIDO" else "pendente"
                self.tree.insert("", "end", values=[index] + list(row), tags=(tag,))

    def salvar_dados(self):
        """Salva um novo registro ou atualiza um existente na planilha."""
        nome = self.entry_usuario.get().strip().upper()
        itm_selecionado = self.combo_item.get().upper()
        qtd = self.entry_qtd.get().strip().upper()

        # Tratamento especial: se for "Outros", o texto extra vira o nome do item
        if itm_selecionado == "OUTROS":
            itm_final = self.entry_extra.get().strip().upper()
            num_not = "-"
        else:
            itm_final = itm_selecionado
            num_not = self.entry_extra.get().strip().upper() if itm_selecionado == "NOTEBOOK" else "-"

        # Validação básica
        if not nome or itm_selecionado == "SELECIONE UM ITEM" or not itm_final:
            self.mostrar_mensagem("PREENCHA TODOS OS CAMPOS", "red")
            return

        try:
            df = pd.read_excel(self.planilha_nome).astype(str) if os.path.exists(self.planilha_nome) else pd.DataFrame(columns=self.colunas[1:])

            if self.edit_mode_index is not None:
                # LÓGICA DE EDIÇÃO: Atualiza a linha selecionada
                status_novo = self.combo_status.get().upper()
                if status_novo == "PENDENTE":
                    data_dev = "-"
                elif status_novo == "DEVOLVIDO" and df.iloc[self.edit_mode_index]["STATUS"] != "DEVOLVIDO":
                    data_dev = datetime.now().strftime("%d/%m/%Y %H:%M")
                else:
                    data_dev = df.iloc[self.edit_mode_index]["DATA DEVOLUÇÃO"]

                df.iloc[self.edit_mode_index] = [nome, itm_final, num_not, qtd, df.iloc[self.edit_mode_index]["DATA EMPRÉSTIMO"], status_novo, data_dev]
                self.mostrar_mensagem("ALTERADO!", "#85c1e9")
            else:
                # LÓGICA DE NOVO REGISTRO: Adiciona ao final
                dt = datetime.now().strftime("%d/%m/%Y %H:%M")
                novo = pd.DataFrame({"USUÁRIO": [nome], "ITEM": [itm_final], "Nº NOTEBOOK": [num_not], "QTD": [qtd], "DATA EMPRÉSTIMO": [dt], "STATUS": ["PENDENTE"], "DATA DEVOLUÇÃO": ["-"]})
                df = pd.concat([df, novo], ignore_index=True)
                self.mostrar_mensagem("SALVO!", "#5dade2")

            df.to_excel(self.planilha_nome, index=False)
            self.limpar_campos()
            self.atualizar_tabela()
        except Exception as e:
            self.mostrar_mensagem(f"ERRO: {e}", "red")

    def preparar_edicao(self):
        """Puxa os dados da tabela para os campos de entrada para permitir editar."""
        selected = self.tree.selection()
        if not selected: return
        vals = self.tree.item(selected)['values']
        self.edit_mode_index = int(vals[0]) # Salva qual linha estamos editando

        self.entry_usuario.delete(0, "end"); self.entry_usuario.insert(0, vals[1])
        self.combo_item.set(vals[2]); self.gerenciar_campos_extras(vals[2])
        self.entry_extra.delete(0, "end"); self.entry_extra.insert(0, vals[3])
        self.entry_qtd.delete(0, "end"); self.entry_qtd.insert(0, vals[4])
        self.combo_status.set(vals[6])

        # Mostra opções de edição
        self.frame_status_edit.pack(pady=5, before=self.lbl_status_msg)
        self.btn_enviar.configure(text="SALVAR ALTERAÇÃO", fg_color="#2e86c1")
        self.btn_cancelar_edit.pack(pady=5)

    def marcar_devolvido(self):
        """Atalho rápido para mudar o status de um item para DEVOLVIDO."""
        selected = self.tree.selection()
        if not selected: return
        idx = int(self.tree.item(selected)['values'][0])
        df = pd.read_excel(self.planilha_nome).astype(str)
        df.loc[idx, 'STATUS'], df.loc[idx, 'DATA DEVOLUÇÃO'] = 'DEVOLVIDO', datetime.now().strftime("%d/%m/%Y %H:%M")
        df.to_excel(self.planilha_nome, index=False); self.atualizar_tabela()

    def excluir_registro(self):
        """Remove a linha selecionada da planilha."""
        selected = self.tree.selection()
        if not selected: return
        idx = int(self.tree.item(selected)['values'][0])
        if messagebox.askyesno("Confirmar", "Excluir registro?"):
            df = pd.read_excel(self.planilha_nome).drop(idx).reset_index(drop=True)
            df.to_excel(self.planilha_nome, index=False); self.atualizar_tabela()

    def limpar_campos(self):
        """Reseta todos os campos do formulário para o estado inicial."""
        self.entry_usuario.delete(0, "end"); self.entry_qtd.delete(0, "end"); self.entry_extra.delete(0, "end")
        self.combo_item.set("SELECIONE UM ITEM"); self.frame_extra.pack_forget(); self.frame_status_edit.pack_forget()
        self.edit_mode_index = None; self.btn_enviar.configure(text="REGISTRAR EMPRÉSTIMO", fg_color="#2874a6")
        self.btn_cancelar_edit.pack_forget(); self.current_user = ""

    def update_frame(self):
        """Atualiza o feed da câmera na interface a cada 15ms."""
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.flip(frame, 1) # Efeito espelho
            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            base_img = Image.fromarray(img_rgb).resize((500, 375))

            # Lógica para mostrar a foto do banco de dados (Overlay) quando reconhece
            if self.show_overlay and self.overlay_image:
                if time.time() < self.overlay_timer:
                    face_thumb = self.overlay_image.copy(); face_thumb.thumbnail((120, 120))
                    base_img.paste(face_thumb, (360, 20))
                else: self.show_overlay = False

            img_tk = ImageTk.PhotoImage(image=base_img)
            self.video_label.configure(image=img_tk, text=""); self.video_label.image = img_tk
        self.after(15, self.update_frame)

    def face_recognition_loop(self):
        """Thread separada para processar o reconhecimento facial sem travar a tela."""
        while True:
            ret, frame = self.cap.read()
            if ret and self.edit_mode_index is None: # Só reconhece se não estiver editando manualmente
                try:
                    # DeepFace busca o rosto na pasta 'base_rostos'
                    res = DeepFace.find(img_path=frame, db_path=self.path_db, model_name='Facenet', enforce_detection=False, silent=True)
                    if len(res) > 0 and not res[0].empty:
                        path_foto = res[0].iloc[0]['identity']
                        name = os.path.basename(path_foto).split('.')[0].upper()
                        if self.current_user != name:
                            self.current_user = name
                            self.entry_usuario.delete(0, "end"); self.entry_usuario.insert(0, name)
                            self.overlay_image = Image.open(path_foto); self.show_overlay = True
                            self.overlay_timer = time.time() + 4
                        self.last_seen_time = time.time()
                except: pass
            time.sleep(0.5) # Evita sobrecarregar o processador

    def gerenciar_campos_extras(self, escolha):
        """Mostra ou esconde campos dependendo do item selecionado."""
        self.frame_extra.pack_forget()
        if escolha in ["NOTEBOOK", "OUTROS"]:
            self.label_extra.configure(text="Número/Descrição:"); self.frame_extra.pack(pady=5)

    def mostrar_mensagem(self, texto, cor="white"):
        """Exibe uma mensagem rápida de feedback por 3 segundos."""
        self.lbl_status_msg.configure(text=texto, text_color=cor)
        self.after(3000, lambda: self.lbl_status_msg.configure(text=""))

    def check_inactivity(self):
        """Limpa o nome do usuário se ele sair da frente da câmera por 5 segundos."""
        if time.time() - self.last_seen_time > 5 and self.current_user != "" and self.edit_mode_index is None:
            self.entry_usuario.delete(0, "end"); self.current_user = ""
        self.after(1000, self.check_inactivity)

    def start_logic(self):
        """Inicia os processos paralelos."""
        threading.Thread(target=self.face_recognition_loop, daemon=True).start()
        self.check_inactivity(); self.update_frame()

if __name__ == "__main__":
    app = AppEmprestimo(); app.mainloop()