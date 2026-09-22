"""Validador de Conformidade de Laboratórios - TI.

Interface moderna em Tkinter para validar softwares instalados, o driver de
vídeo e o IPv4 principal do dispositivo. Cada laboratório possui um JSON
independente na pasta ``configuracoes``.

O pacote ``psutil`` é opcional. Quando instalado, ele melhora a seleção da
interface de rede; sem ele, o aplicativo usa apenas recursos nativos do Python.
"""

from __future__ import annotations

import ctypes
import glob
import json
import os
import platform
import queue
import re
import socket
import subprocess
import sys
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Final
import tkinter as tk
from tkinter import messagebox, ttk

try:
    import psutil
except ImportError:  # O aplicativo continua funcional sem dependências externas.
    psutil = None


# Melhora a nitidez da interface em monitores com escala no Windows.
if platform.system() == "Windows":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


@dataclass(frozen=True)
class Software:
    nome: str
    categoria: str
    caminhos: tuple[str, ...]


@dataclass(frozen=True)
class Laboratorio:
    codigo: str
    nome: str
    descricao: str
    ordem: int
    softwares: tuple[Software, ...]


NOME_DRIVER_VIDEO: Final = "Driver de vídeo"
TEXTO_SELECIONE_LABORATORIO: Final = "Selecione um laboratório..."
VALIDACAO_DRIVER_VIDEO: Final = Software(
    nome=NOME_DRIVER_VIDEO,
    categoria="Hardware",
    caminhos=("Driver do fabricante (Intel, AMD ou NVIDIA)",),
)


class ErroConfiguracao(ValueError):
    """Indica que uma configuração de laboratório está ausente ou inválida."""


def diretorio_aplicacao() -> Path:
    """Retorna a pasta do script ou, no PyInstaller, a pasta do executável."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def localizar_arquivos_configuracao() -> tuple[Path, ...]:
    """Localiza JSONs embutidos e aplica substituições externas por nome."""
    arquivos: dict[str, Path] = {}

    # No executável --onefile, todos os perfis viajam embutidos. Um JSON com o
    # mesmo nome em ``configuracoes`` ao lado do EXE substitui somente aquele
    # perfil, permitindo manutenção sem recompilar o programa.
    pasta_bundle = getattr(sys, "_MEIPASS", None)
    if pasta_bundle:
        pasta_embutida = Path(pasta_bundle) / "configuracoes"
        if pasta_embutida.is_dir():
            arquivos.update(
                {arquivo.name.casefold(): arquivo for arquivo in pasta_embutida.glob("*.json")}
            )

    pasta_externa = diretorio_aplicacao() / "configuracoes"
    if pasta_externa.is_dir():
        arquivos.update(
            {arquivo.name.casefold(): arquivo for arquivo in pasta_externa.glob("*.json")}
        )

    return tuple(arquivos[chave] for chave in sorted(arquivos))


def _carregar_laboratorio(arquivo: Path) -> Laboratorio:
    """Lê e valida um único arquivo de laboratório."""
    try:
        with arquivo.open("r", encoding="utf-8-sig") as configuracao:
            dados = json.load(configuracao)
    except FileNotFoundError as erro:
        raise ErroConfiguracao(
            f"O arquivo não foi encontrado em {arquivo.parent}."
        ) from erro
    except json.JSONDecodeError as erro:
        raise ErroConfiguracao(
            f"JSON inválido na linha {erro.lineno}, coluna {erro.colno}: {erro.msg}"
        ) from erro
    except OSError as erro:
        raise ErroConfiguracao(f"Não foi possível ler {arquivo.name}: {erro}") from erro

    if not isinstance(dados, dict):
        raise ErroConfiguracao("a raiz do JSON deve ser um objeto.")

    codigo = dados.get("codigo")
    nome_laboratorio = dados.get("laboratorio")
    descricao = dados.get("descricao", "")
    ordem = dados.get("ordem", 999)

    if not isinstance(codigo, str) or not codigo.strip():
        raise ErroConfiguracao('o campo "codigo" deve conter um texto.')
    if not isinstance(nome_laboratorio, str) or not nome_laboratorio.strip():
        raise ErroConfiguracao('o campo "laboratorio" deve conter um texto.')
    if not isinstance(descricao, str):
        raise ErroConfiguracao('o campo "descricao" deve conter um texto.')
    if not isinstance(ordem, int) or isinstance(ordem, bool):
        raise ErroConfiguracao('o campo "ordem" deve ser um número inteiro.')
    if not isinstance(dados.get("softwares"), list):
        raise ErroConfiguracao(
            'A configuração deve conter uma lista chamada "softwares".'
        )

    softwares: list[Software] = []
    nomes_utilizados: set[str] = set()

    for indice, item in enumerate(dados["softwares"], start=1):
        referencia = f"softwares[{indice}]"
        if not isinstance(item, dict):
            raise ErroConfiguracao(f"{referencia} deve ser um objeto JSON.")

        ativo = item.get("ativo", True)
        if not isinstance(ativo, bool):
            raise ErroConfiguracao(f'{referencia}.ativo deve ser true ou false.')
        if not ativo:
            continue

        nome = item.get("nome")
        categoria = item.get("categoria")
        caminhos = item.get("caminhos")

        if not isinstance(nome, str) or not nome.strip():
            raise ErroConfiguracao(f'{referencia}.nome deve conter um texto.')
        if not isinstance(categoria, str) or not categoria.strip():
            raise ErroConfiguracao(f'{referencia}.categoria deve conter um texto.')
        if not isinstance(caminhos, list) or not caminhos:
            raise ErroConfiguracao(
                f'{referencia}.caminhos deve ser uma lista com pelo menos um caminho.'
            )

        caminhos_validos: list[str] = []
        for numero, caminho in enumerate(caminhos, start=1):
            if not isinstance(caminho, str) or not caminho.strip():
                raise ErroConfiguracao(
                    f'{referencia}.caminhos[{numero}] deve conter um texto.'
                )
            caminhos_validos.append(caminho.strip())

        nome = nome.strip()
        chave_nome = nome.casefold()
        if chave_nome == NOME_DRIVER_VIDEO.casefold():
            raise ErroConfiguracao(
                f'O nome "{NOME_DRIVER_VIDEO}" é reservado pelo validador.'
            )
        if chave_nome in nomes_utilizados:
            raise ErroConfiguracao(f'O software "{nome}" está duplicado.')
        nomes_utilizados.add(chave_nome)

        softwares.append(
            Software(
                nome=nome,
                categoria=categoria.strip(),
                caminhos=tuple(caminhos_validos),
            )
        )

    if not softwares:
        raise ErroConfiguracao("Nenhum software ativo foi encontrado na configuração.")

    return Laboratorio(
        codigo=codigo.strip(),
        nome=nome_laboratorio.strip(),
        descricao=descricao.strip(),
        ordem=ordem,
        softwares=tuple(softwares),
    )


def carregar_laboratorios() -> tuple[tuple[Laboratorio, ...], tuple[str, ...]]:
    """Carrega todos os perfis válidos e retorna avisos dos arquivos inválidos."""
    arquivos = localizar_arquivos_configuracao()
    pasta_esperada = diretorio_aplicacao() / "configuracoes"
    if not arquivos:
        raise ErroConfiguracao(
            "Nenhum arquivo .json foi encontrado na pasta de configurações:\n"
            f"{pasta_esperada}"
        )

    laboratorios: list[Laboratorio] = []
    avisos: list[str] = []
    codigos: set[str] = set()
    nomes: set[str] = set()

    for arquivo in arquivos:
        try:
            laboratorio = _carregar_laboratorio(arquivo)
            chave_codigo = laboratorio.codigo.casefold()
            chave_nome = laboratorio.nome.casefold()
            if chave_codigo in codigos:
                raise ErroConfiguracao(
                    f'o código "{laboratorio.codigo}" já foi utilizado por outro arquivo.'
                )
            if chave_nome in nomes:
                raise ErroConfiguracao(
                    f'o laboratório "{laboratorio.nome}" está duplicado.'
                )
            codigos.add(chave_codigo)
            nomes.add(chave_nome)
            laboratorios.append(laboratorio)
        except ErroConfiguracao as erro:
            avisos.append(f"{arquivo.name}: {erro}")

    if not laboratorios:
        detalhes = "\n".join(f"• {aviso}" for aviso in avisos)
        raise ErroConfiguracao(
            "Nenhuma configuração válida pôde ser carregada."
            + (f"\n\n{detalhes}" if detalhes else "")
        )

    laboratorios.sort(key=lambda item: _chave_ordenacao_natural(item.nome))
    return tuple(laboratorios), tuple(avisos)


def _chave_ordenacao_natural(texto: str) -> tuple[tuple[int, object], ...]:
    """Ordena nomes sem diferenciar acentos e mantendo números em ordem natural."""
    normalizado = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(caractere)
    ).casefold()
    return tuple(
        (0, int(parte)) if parte.isdigit() else (1, parte)
        for parte in re.split(r"(\d+)", normalizado)
        if parte
    )


PALETAS: Final[dict[str, dict[str, str]]] = {
    "claro": {
        "fundo": "#F3F6FA",
        "superficie": "#FFFFFF",
        "superficie_alt": "#F8FAFC",
        "borda": "#DCE3EC",
        "texto": "#172033",
        "texto_suave": "#667085",
        "primaria": "#155EEF",
        "primaria_hover": "#004EEB",
        "primaria_suave": "#E8F0FF",
        "sucesso": "#079455",
        "sucesso_suave": "#ECFDF3",
        "erro": "#D92D20",
        "erro_suave": "#FEF3F2",
        "aviso": "#DC6803",
        "aviso_suave": "#FFFAEB",
        "neutro": "#475467",
        "neutro_suave": "#F2F4F7",
        "desabilitado": "#98A2B3",
    },
    "escuro": {
        "fundo": "#0D1424",
        "superficie": "#151E2F",
        "superficie_alt": "#1A263A",
        "borda": "#2A3950",
        "texto": "#F5F7FA",
        "texto_suave": "#A8B3C5",
        "primaria": "#4C85FF",
        "primaria_hover": "#76A3FF",
        "primaria_suave": "#1B315E",
        "sucesso": "#47CD89",
        "sucesso_suave": "#173D31",
        "erro": "#FF766F",
        "erro_suave": "#482523",
        "aviso": "#FDB022",
        "aviso_suave": "#493817",
        "neutro": "#C4CCDA",
        "neutro_suave": "#243146",
        "desabilitado": "#667085",
    },
}


def _expandir_variaveis_windows(caminho: str) -> str:
    """Expande tanto $VAR quanto %VAR%, inclusive em testes fora do Windows."""
    expandido = os.path.expandvars(os.path.expanduser(caminho))
    for chave, valor in os.environ.items():
        expandido = expandido.replace(f"%{chave}%", valor)
    return expandido


def localizar_software(software: Software) -> str | None:
    """Retorna o primeiro caminho existente entre as alternativas configuradas."""
    for candidato in software.caminhos:
        candidato = _expandir_variaveis_windows(candidato)
        ocorrencias = glob.glob(candidato)
        if ocorrencias:
            return os.path.normpath(ocorrencias[0])
        if os.path.exists(candidato):
            return os.path.normpath(candidato)
    return None


def _normalizar_texto(texto: object) -> str:
    """Normaliza textos do Windows para comparar nomes em qualquer idioma."""
    valor = unicodedata.normalize("NFKD", str(texto or "").casefold())
    return "".join(caractere for caractere in valor if not unicodedata.combining(caractere))


def _eh_adaptador_basico(adaptador: dict[str, object]) -> bool:
    """Identifica o driver genérico usado quando falta o driver do fabricante."""
    nome = _normalizar_texto(adaptador.get("Name"))
    arquivo_inf = _normalizar_texto(adaptador.get("InfFilename"))
    nomes_basicos = (
        "microsoft basic display adapter",
        "adaptador de video basico da microsoft",
        "adaptador basico de video da microsoft",
    )
    return any(termo in nome for termo in nomes_basicos) or "basicdisplay.inf" in arquivo_inf


def verificar_driver_video() -> tuple[str, str]:
    """Retorna o estado e os detalhes do driver de vídeo instalado no Windows."""
    if platform.system() != "Windows":
        return "erro", "Verificação disponível somente no Windows"

    comando = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "$ErrorActionPreference = 'Stop'; "
        "$adaptadores = @(Get-CimInstance -ClassName Win32_VideoController "
        "| Select-Object Name, DriverVersion, PNPDeviceID, "
        "ConfigManagerErrorCode, Status, InfFilename); "
        "ConvertTo-Json -InputObject $adaptadores -Compress -Depth 3"
    )
    argumentos = [
        "powershell.exe",
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        comando,
    ]
    opcoes: dict[str, object] = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": 20,
        "check": False,
    }
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        opcoes["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        processo = subprocess.run(argumentos, **opcoes)
    except (OSError, subprocess.SubprocessError):
        return "erro", "Não foi possível consultar o driver de vídeo"

    if processo.returncode != 0 or not processo.stdout.strip():
        return "erro", "Não foi possível consultar o driver de vídeo"

    try:
        dados = json.loads(processo.stdout.lstrip("\ufeff").strip())
    except (json.JSONDecodeError, TypeError):
        return "erro", "Resposta inválida ao consultar o driver de vídeo"

    if isinstance(dados, dict):
        adaptadores = [dados]
    elif isinstance(dados, list):
        adaptadores = [item for item in dados if isinstance(item, dict)]
    else:
        adaptadores = []

    if not adaptadores:
        return "falha", "Nenhum adaptador de vídeo foi identificado"

    detalhes: list[str] = []
    problemas: list[str] = []
    for adaptador in adaptadores:
        nome = str(adaptador.get("Name") or "Adaptador de vídeo").strip()
        versao = str(adaptador.get("DriverVersion") or "").strip()
        codigo_bruto = adaptador.get("ConfigManagerErrorCode")
        try:
            codigo_erro = int(codigo_bruto) if codigo_bruto is not None else None
        except (TypeError, ValueError):
            codigo_erro = None

        if _eh_adaptador_basico(adaptador):
            problemas.append(f"{nome} — driver do fabricante ausente")
        elif codigo_erro not in (None, 0):
            problemas.append(f"{nome} — erro do dispositivo (código {codigo_erro})")
        elif not versao:
            problemas.append(f"{nome} — versão do driver não identificada")
        else:
            detalhes.append(f"{nome} — versão {versao}")

    if problemas:
        return "falha", "; ".join(problemas)
    if not detalhes:
        return "falha", "Driver do fabricante não identificado"
    return "conforme", "; ".join(detalhes)


def itens_validacao(laboratorio: Laboratorio) -> tuple[Software, ...]:
    """Inclui as verificações universais antes dos softwares do laboratório."""
    return (VALIDACAO_DRIVER_VIDEO, *laboratorio.softwares)


def obter_ipv4_principal() -> str:
    """Prioriza interfaces físicas ativas sem descartar redes privadas 172.x."""
    termos_virtuais = (
        "virtual",
        "vmware",
        "vbox",
        "hyper-v",
        "vethernet",
        "loopback",
        "docker",
        "wsl",
    )
    candidatos: list[tuple[int, str]] = []

    if psutil is not None:
        try:
            interfaces = psutil.net_if_addrs()
            estatisticas = psutil.net_if_stats()

            for interface, enderecos in interfaces.items():
                status = estatisticas.get(interface)
                if not status or not status.isup:
                    continue

                nome_interface = interface.casefold()
                virtual = any(termo in nome_interface for termo in termos_virtuais)

                for endereco in enderecos:
                    if endereco.family != socket.AF_INET:
                        continue
                    ip = endereco.address
                    if ip.startswith(("127.", "169.254.")):
                        continue
                    prioridade = 1 if virtual else 0
                    candidatos.append((prioridade, ip))

            if candidatos:
                candidatos.sort(key=lambda item: item[0])
                return candidatos[0][1]
        except (OSError, KeyError, AttributeError):
            pass

    # Conectar um socket UDP apenas consulta a rota local; nenhum dado é enviado.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as conexao:
            conexao.connect(("10.255.255.255", 1))
            ip = conexao.getsockname()[0]
            if not ip.startswith(("127.", "169.254.")):
                return ip
    except OSError:
        pass

    try:
        enderecos = socket.gethostbyname_ex(socket.gethostname())[2]
        for ip in enderecos:
            if not ip.startswith(("127.", "169.254.")):
                return ip
    except OSError:
        pass

    return "Não encontrado"


class CartaoResumo(tk.Frame):
    """Cartao compacto usado no resumo superior."""

    def __init__(
        self,
        master: tk.Misc,
        titulo: str,
        valor: str,
        cor_destaque: str,
        **kwargs,
    ) -> None:
        super().__init__(master, bd=0, highlightthickness=1, **kwargs)
        self.cor_destaque = cor_destaque

        self.faixa = tk.Frame(self, width=4, bd=0)
        self.faixa.pack(side="left", fill="y")
        self.faixa.pack_propagate(False)

        self.conteudo = tk.Frame(self, bd=0)
        self.conteudo.pack(side="left", fill="both", expand=True, padx=16, pady=13)

        self.titulo = tk.Label(
            self.conteudo,
            text=titulo.upper(),
            anchor="w",
            font=("Segoe UI", 8, "bold"),
        )
        self.titulo.pack(fill="x")

        # Uma linha dedicada mantem o valor e eventuais acoes alinhados sem
        # depender de coordenadas absolutas. Isso torna o cartao responsivo.
        self.linha_valor = tk.Frame(self.conteudo, bd=0)
        self.linha_valor.pack(fill="x", pady=(6, 0))
        self.linha_valor.columnconfigure(0, weight=1)

        self.valor = tk.Label(
            self.linha_valor,
            text=valor,
            anchor="w",
            font=("Segoe UI Semibold", 16),
        )
        self.valor.grid(row=0, column=0, sticky="ew")

    def aplicar_paleta(self, paleta: dict[str, str]) -> None:
        self.configure(
            bg=paleta["superficie"],
            highlightbackground=paleta["borda"],
            highlightcolor=paleta["borda"],
        )
        self.conteudo.configure(bg=paleta["superficie"])
        self.linha_valor.configure(bg=paleta["superficie"])
        self.faixa.configure(bg=self.cor_destaque)
        self.titulo.configure(
            bg=paleta["superficie"], fg=paleta["texto_suave"]
        )
        self.valor.configure(bg=paleta["superficie"], fg=paleta["texto"])


class ValidadorConformidade(tk.Tk):
    def __init__(
        self,
        laboratorios: tuple[Laboratorio, ...],
        avisos_configuracao: tuple[str, ...] = (),
    ) -> None:
        super().__init__()

        self.title("Validador de Laboratórios - TI")
        self.geometry("1060x760")
        self.minsize(900, 640)
        self.configure(bg=PALETAS["claro"]["fundo"])

        self.tema = "claro"
        self.laboratorios = laboratorios
        self.avisos_configuracao = avisos_configuracao
        self.laboratorio_por_nome = {
            laboratorio.nome: laboratorio for laboratorio in laboratorios
        }
        self.laboratorio_atual: Laboratorio | None = None
        self.softwares: tuple[Software, ...] = ()
        self.software_por_nome: dict[str, Software] = {}
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        self.resultados_por_laboratorio: dict[
            str, dict[str, dict[str, str]]
        ] = {
            laboratorio.codigo: self._criar_resultados_pendentes(
                itens_validacao(laboratorio)
            )
            for laboratorio in self.laboratorios
        }
        self.resultados: dict[str, dict[str, str]] = {}
        self.ultimas_verificacoes: dict[str, str] = {}
        self.cartoes_externos: list[tk.Frame] = []
        self.validacao_em_andamento = False
        self.eventos: queue.Queue[tuple[str, tuple[object, ...]]] = queue.Queue()

        self.laboratorio_var = tk.StringVar(value=TEXTO_SELECIONE_LABORATORIO)
        self.descricao_laboratorio_var = tk.StringVar(
            value=(
                f"{len(self.laboratorios)} ambientes disponíveis • "
                "Escolha um laboratório para iniciar"
            )
        )
        self.ultima_verificacao_var = tk.StringVar(
            value="Última verificação: selecione um laboratório"
        )
        self.ip = obter_ipv4_principal()

        self._criar_icone()
        self._construir_interface()
        self._configurar_estilos()
        self._renderizar_tabela()
        self._atualizar_resumo()
        self._centralizar_janela()
        self.after(50, self._processar_eventos)

        self.bind("<Control-r>", lambda _event: self.verificar_softwares())
        self.bind("<F5>", lambda _event: self.verificar_softwares())

    @staticmethod
    def _criar_resultados_pendentes(
        softwares: tuple[Software, ...],
    ) -> dict[str, dict[str, str]]:
        return {
            software.nome: {"estado": "pendente", "caminho": ""}
            for software in softwares
        }

    def _criar_icone(self) -> None:
        """Cria um pequeno ícone embutido e elimina arquivos PNG obrigatórios."""
        icone = tk.PhotoImage(width=32, height=32)
        icone.put("#155EEF", to=(3, 3, 29, 29))
        icone.put("#FFFFFF", to=(8, 15, 13, 19))
        icone.put("#FFFFFF", to=(12, 18, 16, 22))
        icone.put("#FFFFFF", to=(15, 15, 19, 21))
        icone.put("#FFFFFF", to=(18, 11, 23, 18))
        self.iconphoto(True, icone)
        self._icone_aplicacao = icone

    def _centralizar_janela(self) -> None:
        self.update_idletasks()
        largura = self.winfo_width()
        altura = self.winfo_height()
        x = max(0, (self.winfo_screenwidth() - largura) // 2)
        y = max(0, (self.winfo_screenheight() - altura) // 2)
        self.geometry(f"{largura}x{altura}+{x}+{y}")

    def _novo_cartao(self, master: tk.Misc) -> tuple[tk.Frame, ttk.Frame]:
        externo = tk.Frame(master, bd=0, highlightthickness=1)
        interno = ttk.Frame(externo, style="Card.TFrame")
        interno.pack(fill="both", expand=True)
        self.cartoes_externos.append(externo)
        return externo, interno

    def _construir_interface(self) -> None:
        self.container = ttk.Frame(self, style="App.TFrame", padding=(26, 22, 26, 18))
        self.container.pack(fill="both", expand=True)

        self.container.columnconfigure(0, weight=1)
        self.container.rowconfigure(4, weight=1)

        self._construir_cabecalho()
        self._construir_seletor_laboratorio()
        self._construir_aviso_configuracao()
        self._construir_resumo()
        self._construir_lista()
        self._construir_rodape()

    def _construir_cabecalho(self) -> None:
        cabecalho = ttk.Frame(self.container, style="App.TFrame")
        cabecalho.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        cabecalho.columnconfigure(0, weight=1)

        textos = ttk.Frame(cabecalho, style="App.TFrame")
        textos.grid(row=0, column=0, sticky="w")

        ttk.Label(textos, text="OPERAÇÕES DE TI", style="Eyebrow.TLabel").pack(anchor="w")
        ttk.Label(
            textos,
            text="Validador de conformidade",
            style="Header.TLabel",
        ).pack(anchor="w", pady=(3, 2))
        ttk.Label(
            textos,
            text="Valide os softwares essenciais e o driver de vídeo do dispositivo.",
            style="Subtitle.TLabel",
        ).pack(anchor="w")

        acoes = ttk.Frame(cabecalho, style="App.TFrame")
        acoes.grid(row=0, column=1, sticky="e")

        dispositivo = ttk.Frame(acoes, style="Device.TFrame", padding=(12, 7))
        dispositivo.pack(side="left", padx=(0, 10))
        ttk.Label(dispositivo, text="DISPOSITIVO", style="DeviceCaption.TLabel").pack(anchor="w")
        ttk.Label(
            dispositivo,
            text=platform.node().upper() or "LOCAL",
            style="DeviceValue.TLabel",
        ).pack(anchor="w")

        self.botao_tema = ttk.Button(
            acoes,
            text="☾  Tema escuro",
            command=self.trocar_tema,
            style="Ghost.TButton",
        )
        self.botao_tema.pack(side="left")

    def _construir_seletor_laboratorio(self) -> None:
        externo, seletor = self._novo_cartao(self.container)
        externo.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        seletor.columnconfigure(1, weight=1)

        ttk.Label(
            seletor,
            text="LABORATÓRIO",
            style="SelectorCaption.TLabel",
        ).grid(row=0, column=0, sticky="nw", padx=(18, 12), pady=(17, 0))

        self.seletor_laboratorio = ttk.Combobox(
            seletor,
            textvariable=self.laboratorio_var,
            values=(
                TEXTO_SELECIONE_LABORATORIO,
                *(laboratorio.nome for laboratorio in self.laboratorios),
            ),
            state="readonly",
            style="Lab.TCombobox",
            cursor="hand2",
        )
        self.seletor_laboratorio.grid(
            row=0, column=1, sticky="ew", padx=(0, 18), pady=(12, 6)
        )
        self.seletor_laboratorio.bind(
            "<<ComboboxSelected>>", self._ao_selecionar_laboratorio
        )

        self.label_descricao_laboratorio = ttk.Label(
            seletor,
            textvariable=self.descricao_laboratorio_var,
            style="SelectorDescription.TLabel",
            anchor="w",
        )
        self.label_descricao_laboratorio.grid(
            row=1, column=1, sticky="w", padx=(1, 18), pady=(0, 12)
        )

    def _construir_aviso_configuracao(self) -> None:
        if not self.avisos_configuracao:
            return

        quantidade = len(self.avisos_configuracao)
        texto = (
            "1 configuração foi ignorada. Os demais ambientes continuam disponíveis."
            if quantidade == 1
            else f"{quantidade} configurações foram ignoradas. Os demais ambientes continuam disponíveis."
        )
        aviso = ttk.Frame(
            self.container,
            style="Warning.TFrame",
            padding=(14, 9),
        )
        aviso.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        aviso.columnconfigure(0, weight=1)
        ttk.Label(
            aviso,
            text=f"⚠  {texto}",
            style="Warning.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            aviso,
            text="Ver detalhes",
            command=self._mostrar_avisos_configuracao,
            style="Warning.TButton",
            cursor="hand2",
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))

    def _mostrar_avisos_configuracao(self) -> None:
        detalhes = "\n".join(
            f"• {aviso}" for aviso in self.avisos_configuracao
        )
        messagebox.showwarning(
            "Configurações ignoradas",
            detalhes,
            parent=self,
        )

    def _construir_resumo(self) -> None:
        resumo = ttk.Frame(self.container, style="App.TFrame")
        resumo.grid(row=3, column=0, sticky="ew", pady=(0, 16))
        for coluna in range(4):
            resumo.columnconfigure(coluna, weight=1, uniform="resumo")

        paleta = PALETAS[self.tema]
        self.cartao_geral = CartaoResumo(
            resumo, "Status geral", "Selecione", paleta["primaria"]
        )
        self.cartao_conformes = CartaoResumo(
            resumo, "Conformes", "—", paleta["sucesso"]
        )
        self.cartao_falhas = CartaoResumo(
            resumo, "Não conformes", "—", paleta["erro"]
        )
        self.cartao_ip = CartaoResumo(
            resumo, "IPv4 do dispositivo", self.ip, paleta["primaria"]
        )
        self.cartoes_resumo = (
            self.cartao_geral,
            self.cartao_conformes,
            self.cartao_falhas,
            self.cartao_ip,
        )

        for coluna, cartao in enumerate(self.cartoes_resumo):
            margem_direita = 0 if coluna == 3 else 10
            cartao.grid(row=0, column=coluna, sticky="nsew", padx=(0, margem_direita))

        self.botao_copiar_ip = ttk.Button(
            self.cartao_ip.linha_valor,
            text="Copiar",
            command=self.copiar_ip,
            style="Inline.TButton",
            cursor="hand2",
            width=7,
        )
        self.botao_copiar_ip.grid(row=0, column=1, sticky="e", padx=(8, 0))
        self.cartao_ip.valor.configure(font=("Segoe UI Semibold", 14))

    def _construir_lista(self) -> None:
        externo, cartao = self._novo_cartao(self.container)
        externo.grid(row=4, column=0, sticky="nsew")
        cartao.columnconfigure(0, weight=1)
        cartao.rowconfigure(1, weight=1)

        barra = ttk.Frame(cartao, style="Card.TFrame", padding=(18, 15, 18, 12))
        barra.grid(row=0, column=0, sticky="ew")
        barra.columnconfigure(0, weight=1)

        titulo = ttk.Frame(barra, style="Card.TFrame")
        titulo.grid(row=0, column=0, sticky="w")
        ttk.Label(titulo, text="Itens monitorados", style="Section.TLabel").pack(
            side="left"
        )
        self.label_quantidade = ttk.Label(
            titulo,
            text="Selecione um ambiente",
            style="Count.TLabel",
        )
        self.label_quantidade.pack(side="left", padx=(9, 0))

        ferramentas = ttk.Frame(barra, style="Card.TFrame")
        ferramentas.grid(row=0, column=1, sticky="e")

        self.botao_verificar = ttk.Button(
            ferramentas,
            text="Validar agora",
            command=self.verificar_softwares,
            style="Primary.TButton",
            cursor="hand2",
            state="disabled",
        )
        self.botao_verificar.pack(side="left")

        tabela_frame = ttk.Frame(cartao, style="Card.TFrame", padding=(18, 0, 18, 14))
        tabela_frame.grid(row=1, column=0, sticky="nsew")
        tabela_frame.columnconfigure(0, weight=1)
        tabela_frame.rowconfigure(0, weight=1)

        colunas = ("software", "categoria", "caminho", "status")
        self.tabela = ttk.Treeview(
            tabela_frame,
            columns=colunas,
            show="headings",
            style="Software.Treeview",
            selectmode="browse",
        )
        self.tabela.heading("software", text="ITEM", anchor="w")
        self.tabela.heading("categoria", text="CATEGORIA", anchor="w")
        self.tabela.heading("caminho", text="LOCAL IDENTIFICADO / ESPERADO", anchor="w")
        self.tabela.heading("status", text="STATUS", anchor="w")

        self.tabela.column("software", width=220, minwidth=160, anchor="w")
        self.tabela.column("categoria", width=135, minwidth=110, anchor="w")
        self.tabela.column("caminho", width=390, minwidth=220, anchor="w")
        self.tabela.column("status", width=145, minwidth=130, anchor="w", stretch=False)

        rolagem = ttk.Scrollbar(
            tabela_frame, orient="vertical", command=self.tabela.yview
        )
        self.tabela.configure(yscrollcommand=rolagem.set)
        self.tabela.grid(row=0, column=0, sticky="nsew")
        rolagem.grid(row=0, column=1, sticky="ns")

    def _construir_rodape(self) -> None:
        rodape = ttk.Frame(self.container, style="App.TFrame")
        rodape.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        rodape.columnconfigure(0, weight=1)

        self.label_ultima_verificacao = ttk.Label(
            rodape,
            textvariable=self.ultima_verificacao_var,
            style="Footer.TLabel",
        )
        self.label_ultima_verificacao.grid(row=0, column=0, sticky="e")

    def _configurar_estilos(self) -> None:
        p = PALETAS[self.tema]
        self.configure(bg=p["fundo"])

        self.style.configure("App.TFrame", background=p["fundo"])
        self.style.configure("Card.TFrame", background=p["superficie"])
        self.style.configure("Device.TFrame", background=p["superficie_alt"])
        self.style.configure("Warning.TFrame", background=p["aviso_suave"])
        self.style.configure(
            "Warning.TLabel",
            background=p["aviso_suave"],
            foreground=p["aviso"],
            font=("Segoe UI", 8, "bold"),
        )

        self.style.configure(
            "Eyebrow.TLabel",
            background=p["fundo"],
            foreground=p["primaria"],
            font=("Segoe UI", 8, "bold"),
        )
        self.style.configure(
            "Header.TLabel",
            background=p["fundo"],
            foreground=p["texto"],
            font=("Segoe UI Semibold", 22),
        )
        self.style.configure(
            "Subtitle.TLabel",
            background=p["fundo"],
            foreground=p["texto_suave"],
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "DeviceCaption.TLabel",
            background=p["superficie_alt"],
            foreground=p["texto_suave"],
            font=("Segoe UI", 7, "bold"),
        )
        self.style.configure(
            "DeviceValue.TLabel",
            background=p["superficie_alt"],
            foreground=p["texto"],
            font=("Segoe UI Semibold", 9),
        )
        self.style.configure(
            "SelectorCaption.TLabel",
            background=p["superficie"],
            foreground=p["texto_suave"],
            font=("Segoe UI", 8, "bold"),
        )
        self.style.configure(
            "SelectorDescription.TLabel",
            background=p["superficie"],
            foreground=p["texto_suave"],
            font=("Segoe UI", 8),
        )
        self.style.configure(
            "Lab.TCombobox",
            fieldbackground=p["superficie_alt"],
            background=p["superficie_alt"],
            foreground=p["texto"],
            arrowcolor=p["primaria"],
            bordercolor=p["borda"],
            lightcolor=p["borda"],
            darkcolor=p["borda"],
            padding=(9, 6),
            font=("Segoe UI Semibold", 9),
        )
        self.style.map(
            "Lab.TCombobox",
            fieldbackground=[
                ("readonly", p["superficie_alt"]),
                ("disabled", p["neutro_suave"]),
            ],
            foreground=[
                ("readonly", p["texto"]),
                ("disabled", p["desabilitado"]),
            ],
            selectbackground=[("readonly", p["superficie_alt"])],
            selectforeground=[("readonly", p["texto"])],
        )
        self.style.configure(
            "Section.TLabel",
            background=p["superficie"],
            foreground=p["texto"],
            font=("Segoe UI Semibold", 12),
        )
        self.style.configure(
            "Count.TLabel",
            background=p["primaria_suave"],
            foreground=p["primaria"],
            font=("Segoe UI", 8, "bold"),
            padding=(7, 3),
        )
        self.style.configure(
            "Footer.TLabel",
            background=p["fundo"],
            foreground=p["texto_suave"],
            font=("Segoe UI", 8),
        )

        self._estilizar_botao(
            "Primary.TButton", p["primaria"], "#FFFFFF", p["primaria_hover"]
        )
        self._estilizar_botao(
            "Ghost.TButton", p["superficie_alt"], p["texto"], p["borda"]
        )
        self._estilizar_botao(
            "Inline.TButton", p["primaria_suave"], p["primaria"], p["borda"], pequeno=True
        )
        self._estilizar_botao(
            "Warning.TButton", p["aviso_suave"], p["aviso"], p["borda"], pequeno=True
        )

        self.style.configure(
            "Software.Treeview",
            background=p["superficie"],
            fieldbackground=p["superficie"],
            foreground=p["texto"],
            rowheight=37,
            borderwidth=0,
            relief="flat",
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "Software.Treeview.Heading",
            background=p["superficie_alt"],
            foreground=p["texto_suave"],
            borderwidth=0,
            relief="flat",
            font=("Segoe UI", 8, "bold"),
            padding=(8, 8),
        )
        self.style.map(
            "Software.Treeview",
            background=[("selected", p["primaria_suave"])],
            foreground=[("selected", p["texto"])],
        )
        self.style.map(
            "Software.Treeview.Heading",
            background=[("active", p["superficie_alt"])],
        )

        for externo in self.cartoes_externos:
            externo.configure(
                bg=p["superficie"],
                highlightbackground=p["borda"],
                highlightcolor=p["borda"],
            )
        for cartao in self.cartoes_resumo:
            cartao.aplicar_paleta(p)

        self._configurar_tags_tabela()

    def _estilizar_botao(
        self,
        nome: str,
        fundo: str,
        texto: str,
        hover: str,
        pequeno: bool = False,
    ) -> None:
        padding = (9, 4) if pequeno else (13, 8)
        fonte = ("Segoe UI", 8, "bold") if pequeno else ("Segoe UI Semibold", 9)
        self.style.configure(
            nome,
            background=fundo,
            foreground=texto,
            borderwidth=0,
            focusthickness=1,
            focuscolor=fundo,
            padding=padding,
            font=fonte,
        )
        self.style.map(
            nome,
            background=[
                ("disabled", PALETAS[self.tema]["borda"]),
                ("pressed", hover),
                ("active", hover),
            ],
            foreground=[
                ("disabled", PALETAS[self.tema]["desabilitado"]),
                ("active", texto),
            ],
        )

    def _configurar_tags_tabela(self) -> None:
        p = PALETAS[self.tema]
        self.tabela.tag_configure("par", background=p["superficie"])
        self.tabela.tag_configure("impar", background=p["superficie_alt"])
        self.tabela.tag_configure("conforme", background=p["sucesso_suave"])
        self.tabela.tag_configure("falha", background=p["erro_suave"])
        self.tabela.tag_configure("erro", background=p["aviso_suave"])
        self.tabela.tag_configure("verificando", background=p["primaria_suave"])
        self.tabela.tag_configure(
            "vazio",
            background=p["superficie"],
            foreground=p["texto_suave"],
        )

    def trocar_tema(self) -> None:
        self.tema = "escuro" if self.tema == "claro" else "claro"
        texto = "☀  Tema claro" if self.tema == "escuro" else "☾  Tema escuro"
        self.botao_tema.configure(text=texto)
        self._configurar_estilos()
        self._renderizar_tabela()
        self._atualizar_resumo()

    def _ao_selecionar_laboratorio(self, _evento: tk.Event | None = None) -> None:
        if self.validacao_em_andamento:
            if self.laboratorio_atual is not None:
                self.laboratorio_var.set(self.laboratorio_atual.nome)
            return

        selecionado = self.laboratorio_por_nome.get(self.laboratorio_var.get())
        if selecionado is None:
            self._limpar_selecao_laboratorio()
            return
        if selecionado == self.laboratorio_atual:
            return

        self.laboratorio_atual = selecionado
        self.softwares = itens_validacao(selecionado)
        self.software_por_nome = {
            software.nome: software for software in self.softwares
        }
        self.resultados = self.resultados_por_laboratorio[selecionado.codigo]
        self.descricao_laboratorio_var.set(
            f"{selecionado.descricao} • {len(self.softwares)} itens monitorados"
        )
        self.label_quantidade.configure(text=f"{len(self.softwares)} itens")

        ultima = self.ultimas_verificacoes.get(selecionado.codigo)
        texto_ultima = ultima or "ainda não realizada"
        self.ultima_verificacao_var.set(f"Última verificação: {texto_ultima}")

        estados = {resultado["estado"] for resultado in self.resultados.values()}
        texto_botao = (
            "Validar novamente"
            if estados & {"conforme", "falha", "erro"}
            else "Validar agora"
        )
        self.botao_verificar.configure(state="normal", text=texto_botao)
        self._renderizar_tabela()
        self._atualizar_resumo()

    def _limpar_selecao_laboratorio(self) -> None:
        self.laboratorio_atual = None
        self.softwares = ()
        self.software_por_nome = {}
        self.resultados = {}
        self.laboratorio_var.set(TEXTO_SELECIONE_LABORATORIO)
        self.descricao_laboratorio_var.set(
            f"{len(self.laboratorios)} ambientes disponíveis • "
            "Escolha um laboratório para iniciar"
        )
        self.label_quantidade.configure(text="Selecione um ambiente")
        self.ultima_verificacao_var.set(
            "Última verificação: selecione um laboratório"
        )
        self.botao_verificar.configure(state="disabled", text="Validar agora")
        self._renderizar_tabela()
        self._atualizar_resumo()

    @staticmethod
    def _texto_status(estado: str) -> str:
        return {
            "pendente": "○  Pendente",
            "verificando": "◌  Verificando",
            "conforme": "✓  Conforme",
            "falha": "×  Não encontrado",
            "erro": "⚠  Não verificado",
        }.get(estado, "○  Pendente")

    def _renderizar_tabela(self) -> None:
        if not hasattr(self, "tabela"):
            return

        selecao = self.tabela.selection()
        selecionado = selecao[0] if selecao else None
        self.tabela.delete(*self.tabela.get_children())

        if self.laboratorio_atual is None:
            self.tabela.insert(
                "",
                "end",
                iid="__sem_laboratorio__",
                values=(
                    "Selecione um laboratório",
                    "—",
                    "Os itens monitorados serão exibidos após a seleção.",
                    "○  Aguardando",
                ),
                tags=("vazio",),
            )
            return

        for indice, software in enumerate(self.softwares):
            resultado = self.resultados[software.nome]
            estado = resultado["estado"]
            caminho = resultado["caminho"] or software.caminhos[0]
            tag = estado if estado != "pendente" else ("par" if indice % 2 == 0 else "impar")

            self.tabela.insert(
                "",
                "end",
                iid=software.nome,
                values=(
                    software.nome,
                    software.categoria,
                    caminho,
                    self._texto_status(estado),
                ),
                tags=(tag,),
            )

        if selecionado and self.tabela.exists(selecionado):
            self.tabela.selection_set(selecionado)

    def _atualizar_resumo(self) -> None:
        if self.laboratorio_atual is None:
            p = PALETAS[self.tema]
            self.cartao_geral.valor.configure(text="Selecione", fg=p["neutro"])
            self.cartao_conformes.valor.configure(text="—", fg=p["texto_suave"])
            self.cartao_falhas.valor.configure(text="—", fg=p["texto_suave"])
            self.cartao_ip.valor.configure(fg=p["texto"])
            return

        estados = [resultado["estado"] for resultado in self.resultados.values()]
        conformes = estados.count("conforme")
        falhas = estados.count("falha")
        erros = estados.count("erro")
        nao_conformes = falhas + erros
        verificados = conformes + nao_conformes

        self.cartao_conformes.valor.configure(
            text=f"{conformes} de {len(self.softwares)}"
        )
        self.cartao_falhas.valor.configure(text=str(nao_conformes))

        p = PALETAS[self.tema]
        if self.validacao_em_andamento:
            texto_geral = "Verificando"
            cor_geral = p["primaria"]
        elif verificados == 0:
            texto_geral = "Aguardando"
            cor_geral = p["neutro"]
        elif nao_conformes == 0 and verificados == len(self.softwares):
            texto_geral = "Em conformidade"
            cor_geral = p["sucesso"]
        else:
            texto_geral = "Requer atenção"
            cor_geral = p["erro"]

        self.cartao_geral.valor.configure(text=texto_geral, fg=cor_geral)
        self.cartao_conformes.valor.configure(fg=p["sucesso"])
        self.cartao_falhas.valor.configure(
            fg=p["erro"] if nao_conformes else p["texto"]
        )
        self.cartao_ip.valor.configure(fg=p["texto"])

    def copiar_ip(self) -> None:
        if self.ip == "Não encontrado":
            self.botao_copiar_ip.configure(text="Sem IP")
            self.after(1600, lambda: self.botao_copiar_ip.configure(text="Copiar"))
            return

        self.clipboard_clear()
        self.clipboard_append(self.ip)
        self.update_idletasks()
        self.botao_copiar_ip.configure(text="Copiado")
        self.after(1600, lambda: self.botao_copiar_ip.configure(text="Copiar"))

    def verificar_softwares(self) -> None:
        if self.validacao_em_andamento or self.laboratorio_atual is None:
            if self.laboratorio_atual is None:
                self.seletor_laboratorio.focus_set()
            return

        self.validacao_em_andamento = True
        self.botao_verificar.configure(state="disabled", text="Validando...")
        self.seletor_laboratorio.configure(state="disabled")
        codigo_laboratorio = self.laboratorio_atual.codigo
        softwares = self.softwares

        for resultado in self.resultados.values():
            resultado["estado"] = "verificando"
            resultado["caminho"] = ""

        self._renderizar_tabela()
        self._atualizar_resumo()

        threading.Thread(
            target=self._tarefa_validacao,
            args=(codigo_laboratorio, softwares),
            daemon=True,
        ).start()

    def _tarefa_validacao(
        self,
        codigo_laboratorio: str,
        softwares: tuple[Software, ...],
    ) -> None:
        for software in softwares:
            if software.nome == NOME_DRIVER_VIDEO:
                estado, caminho_exibido = verificar_driver_video()
            else:
                caminho = localizar_software(software)
                estado = "conforme" if caminho else "falha"
                caminho_exibido = caminho or ""
            self.eventos.put(
                (
                    "resultado_validacao",
                    (
                        codigo_laboratorio,
                        software.nome,
                        estado,
                        caminho_exibido,
                    ),
                )
            )
        self.eventos.put(("fim_validacao", (codigo_laboratorio,)))

    def _aplicar_resultado(
        self,
        codigo_laboratorio: str,
        nome: str,
        estado: str,
        caminho: str,
    ) -> None:
        resultados = self.resultados_por_laboratorio.get(codigo_laboratorio)
        if resultados is None or nome not in resultados:
            return
        resultados[nome] = {"estado": estado, "caminho": caminho}

        if (
            self.laboratorio_atual is None
            or codigo_laboratorio != self.laboratorio_atual.codigo
        ):
            return

        if self.tabela.exists(nome):
            software = self.software_por_nome[nome]
            caminho_exibido = caminho or software.caminhos[0]
            self.tabela.item(
                nome,
                values=(
                    software.nome,
                    software.categoria,
                    caminho_exibido,
                    self._texto_status(estado),
                ),
                tags=(estado,),
            )
        self._atualizar_resumo()

    def _finalizar_validacao(self, codigo_laboratorio: str) -> None:
        if (
            self.laboratorio_atual is None
            or codigo_laboratorio != self.laboratorio_atual.codigo
        ):
            return

        self.validacao_em_andamento = False
        self.botao_verificar.configure(state="normal", text="Validar novamente")
        self.seletor_laboratorio.configure(state="readonly")
        agora = time.strftime("%d/%m/%Y às %H:%M:%S")
        self.ultimas_verificacoes[codigo_laboratorio] = agora
        self.ultima_verificacao_var.set(f"Última verificação: {agora}")

        self._atualizar_resumo()

    def _processar_eventos(self) -> None:
        """Aplica na thread da interface os resultados produzidos em segundo plano."""
        try:
            while True:
                evento, argumentos = self.eventos.get_nowait()
                if evento == "resultado_validacao":
                    self._aplicar_resultado(*argumentos)
                elif evento == "fim_validacao":
                    self._finalizar_validacao(*argumentos)
        except queue.Empty:
            pass

        if self.winfo_exists():
            self.after(50, self._processar_eventos)


def main() -> int:
    try:
        laboratorios, avisos = carregar_laboratorios()
    except ErroConfiguracao as erro:
        janela_erro = tk.Tk()
        janela_erro.withdraw()
        try:
            messagebox.showerror(
                "Configuração de laboratórios inválida",
                str(erro),
                parent=janela_erro,
            )
        finally:
            janela_erro.destroy()
        return 1

    app = ValidadorConformidade(laboratorios, avisos)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
