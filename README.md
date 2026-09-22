# Validador de Conformidade de Laboratórios

Aplicação desktop em Python e Tkinter para verificar a conformidade de computadores dos laboratórios. O programa valida os softwares esperados, o driver de vídeo, a ativação do Windows e o endereço IPv4 principal do dispositivo.

## Funcionalidades

- seleção de laboratório em ordem alfabética;
- perfis independentes em arquivos JSON;
- validação de softwares por um ou mais caminhos possíveis;
- verificação do driver de vídeo do fabricante;
- verificação do estado de ativação do Windows, incluindo ambientes KMS;
- identificação do IPv4 principal;
- resumo de itens conformes e não conformes;
- temas claro e escuro;
- avisos não bloqueantes para configurações inválidas.

## Estrutura

```text
ValidadorConformidade/
├── configuracoes/
│   ├── adm_padrao.json
│   ├── living.json
│   ├── predio_30a_212_215.json
│   ├── predio_30a_313_320.json
│   ├── predio_30d_s1_02_05.json
│   ├── predio_30f_201.json
│   └── predio_30f_211_212.json
├── validador_conformidade.py
├── requirements.txt
└── README.md
```

## Como executar

Requer Python 3.10 ou superior.

```powershell
python -m pip install -r requirements.txt
python validador_conformidade.py
```

O pacote `psutil` melhora a identificação da interface de rede, mas o programa continua funcional sem ele.

## Configuração dos laboratórios

Cada arquivo da pasta `configuracoes` representa um ambiente. Os campos principais são:

- `codigo`: identificador único do perfil;
- `laboratorio`: nome apresentado no seletor;
- `descricao`: descrição exibida na interface;
- `softwares`: lista de itens e caminhos aceitos;
- `ativo`: permite ignorar um software sem removê-lo do JSON.

Após alterar um JSON, reinicie o programa para carregar a nova configuração.

## Gerar executável no Windows

Com o PyInstaller instalado:

```powershell
python -m pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name ValidadorLaboratorios --add-data "configuracoes;configuracoes" validador_conformidade.py
```

O executável será criado na pasta `dist`.
