# ValidadorLaboratorios

Aplicativo desktop para validar softwares esperados, driver de vídeo do fabricante, ativação do Windows e IPv4 principal dos computadores dos laboratórios.

## Versão Java

A versão principal fica em `src/ValidadorLaboratorios.java` e usa Swing, sem dependências externas. Ela mantém os arquivos JSON da pasta `configuracoes` e permite escolher o laboratório, alternar o tema, copiar o IPv4 e consultar o resultado de cada item. A verificação ocorre em segundo plano para manter a interface responsiva.

### Gerar o JAR no Windows

Instale um **JDK 17 ou superior** no computador de compilação e execute `gerar_jar.bat` na pasta do projeto. O script compila o Java, embute todos os JSONs, verifica os perfis e cria `dist\ValidadorLaboratorios.jar`. Se a unidade `J:` estiver disponível, também copia o JAR para `J:\C\Certificação Imagem\Validador`.

No computador cliente, é necessário **Java 17 ou superior** para abrir o JAR:

```bat
java -jar ValidadorLaboratorios.jar
```

O arquivo `executar_jar.bat` abre o JAR a partir da pasta `dist` ou da mesma pasta do `.bat`.

Os JSONs embutidos funcionam mesmo sem a pasta `configuracoes` ao lado do JAR. Para alterar um perfil sem recompilar, crie uma pasta `configuracoes` ao lado do JAR e coloque nela um JSON com o mesmo nome; esse arquivo externo substitui apenas o perfil correspondente. Reinicie o aplicativo após editar um JSON.

Para conferir as configurações sem abrir a janela:

```bat
java -jar ValidadorLaboratorios.jar --check-config
```

O `.jar` não elimina a necessidade de validação pelas políticas de segurança da organização. Verifique com a equipe de segurança o alerta específico do antivírus antes de distribuí-lo.

## Configuração

Cada arquivo JSON define `codigo`, `laboratorio`, `descricao` e `softwares`. Cada software ativo tem `nome`, `categoria` e uma lista de `caminhos` alternativos. O campo `ativo: false` ignora o item. Driver de vídeo e ativação do Windows são verificados em todos os perfis.

## Executar pelo VS Code

Você pode iniciar `src/ValidadorLaboratorios.java` no VS Code. O programa procura os JSONs na pasta `configuracoes` do projeto, inclusive quando o editor usa `src` como diretório de execução. Para distribuir, use o arquivo gerado por `gerar_jar.bat`.
