# ValidadorLaboratorios

Aplicativo desktop para validar softwares esperados, driver de vídeo do fabricante, ativação do Windows e IPv4 principal dos computadores dos laboratórios.

## Versão Java

A versão principal fica em `src/ValidadorLaboratorios.java` e usa Swing, sem dependências externas. Ela mantém os arquivos JSON da pasta `configuracoes` e permite escolher o laboratório, alternar o tema, copiar o IPv4 e consultar o resultado de cada item. A verificação ocorre em segundo plano para manter a interface responsiva.

### Gerar a versão portátil (clientes sem Java)

Execute `gerar_portatil.bat` em um **Windows com JDK 17 ou superior**. O script cria `dist\ValidadorLaboratorios-portatil` com `ValidadorLaboratorios.exe`, `executar_portatil.bat`, o JAR e a subpasta `runtime` contendo o Java necessário. Ele copia a pasta para `J:\C\Certificação Imagem\Validador\ValidadorLaboratorios-portatil` se `J:` estiver acessível. É preciso copiar **a pasta inteira**, não somente o `.exe`. No cliente, abra:

```text
J:\C\Certificação Imagem\Validador\ValidadorLaboratorios-portatil\ValidadorLaboratorios.exe
```

O computador cliente não precisa instalar Java. Também é possível executar `executar_portatil.bat` dentro da pasta portátil; ele usa o Java incluído em `runtime`, sem depender da associação de arquivos `.jar` do Windows. Para atualizar o programa, gere a pasta novamente no computador de compilação. `executar_jar.bat` abre a versão portátil quando ela existir; caso contrário, usa o JAR com o Java instalado. O arquivo `.exe` antigo e o `.jar` na pasta `Validador` continuam sendo arquivos diferentes da versão portátil.

Para conferir a ativação no cliente usando o runtime empacotado, execute no terminal a partir da pasta portátil:

```bat
runtime\bin\java.exe -jar app\ValidadorLaboratorios.jar --check-activation
```

### Gerar o JAR no Windows

Instale um **JDK 17 ou superior** no computador de compilação e execute `gerar_jar.bat` na pasta do projeto. O script compila o Java, embute todos os JSONs, verifica os perfis e cria `dist\ValidadorLaboratorios.jar`. Se a unidade `J:` estiver disponível, também copia o JAR para `J:\C\Certificação Imagem\Validador`.

No computador cliente, é necessário **Java 17 ou superior** para abrir o JAR:

```bat
java -jar ValidadorLaboratorios.jar
```

O arquivo `executar_jar.bat` abre a versão portátil se estiver disponível; caso contrário, abre o JAR a partir de `dist` ou da mesma pasta do `.bat`.

Os JSONs embutidos funcionam mesmo sem a pasta `configuracoes` ao lado do JAR. Para alterar um perfil sem recompilar, crie uma pasta `configuracoes` ao lado do JAR e coloque nela um JSON com o mesmo nome; esse arquivo externo substitui apenas o perfil correspondente. Reinicie o aplicativo após editar um JSON.

Para conferir as configurações sem abrir a janela:

```bat
java -jar ValidadorLaboratorios.jar --check-config
```

Para diagnosticar a ativação do Windows sem abrir a janela:

```bat
java -jar ValidadorLaboratorios.jar --check-activation
```

O resultado indica `conforme`, `falha` ou `erro`. Se as duas consultas à licença falharem, a mensagem apresenta as causas retornadas pelo CIM e pelo SLMGR.

O `.jar` não elimina a necessidade de validação pelas políticas de segurança da organização. Verifique com a equipe de segurança o alerta específico do antivírus antes de distribuí-lo.

## Configuração

Cada arquivo JSON define `codigo`, `laboratorio`, `descricao` e `softwares`. Cada software ativo tem `nome`, `categoria` e uma lista de `caminhos` alternativos. Opcionalmente, `appx` indica nomes de pacotes MSIX para consultar, como `MSTeams`. O campo `ativo: false` ignora o item. Driver de vídeo e ativação do Windows são verificados em todos os perfis.

## Executar pelo VS Code

Você pode iniciar `src/ValidadorLaboratorios.java` no VS Code. O programa procura os JSONs na pasta `configuracoes` do projeto, inclusive quando o editor usa `src` como diretório de execução. Para distribuir em computadores sem Java, use a pasta gerada por `gerar_portatil.bat`.
