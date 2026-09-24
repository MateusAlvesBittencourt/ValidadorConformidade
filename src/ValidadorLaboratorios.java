import javax.swing.*;
import javax.swing.table.*;
import java.awt.*;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.text.Normalizer;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.regex.*;
import java.util.jar.*;

/** Versão Java do validador de laboratórios. Requer Java 17. */
public final class ValidadorLaboratorios extends JFrame {
    private static final long serialVersionUID = 1L;
    record Software(String nome, String categoria, List<String> caminhos) {}
    record Laboratorio(String codigo, String nome, String descricao, List<Software> softwares) {}
    record Resultado(String estado, String detalhe) {}
    record Leitura(List<Laboratorio> laboratorios, List<String> avisos) {}
    private static final Software VIDEO = new Software("Driver de vídeo", "Hardware", List.of("Driver do fabricante (Intel, AMD ou NVIDIA)"));
    private static final Software ATIVACAO = new Software("Ativação do Windows", "Sistema operacional", List.of("Windows ativado e licenciado"));
    private final Leitura leitura;
    private final JComboBox<String> seletor = new JComboBox<>();
    private final DefaultTableModel modelo = new DefaultTableModel(new String[]{"ITEM", "CATEGORIA", "LOCAL IDENTIFICADO / ESPERADO", "STATUS"}, 0) {
        @Override
        public boolean isCellEditable(int row, int column) { return false; }
    };
    private final JTable tabela = new JTable(modelo);
    private final JLabel titulo = new JLabel("ValidadorLaboratorios");
    private final JLabel descricao = new JLabel("Escolha um laboratório para iniciar");
    private final JLabel geral = new JLabel("Selecione");
    private final JLabel conformes = new JLabel("—");
    private final JLabel falhas = new JLabel("—");
    private final JLabel ip = new JLabel(ipPrincipal());
    private final JLabel dispositivo = rotulo(host().toUpperCase(Locale.ROOT), 12, true);
    private final JLabel quantidade = new JLabel("Selecione um ambiente");
    private final JLabel ultima = new JLabel("Última verificação: selecione um laboratório");
    private final JButton validar = new JButton("Validar agora");
    private final JButton tema = new JButton("☾  Tema escuro");
    private final JButton copiar = new JButton("Copiar");
    private final Map<String, Map<String, Resultado>> resultados = new HashMap<>();
    private final Map<String, String> ultimas = new HashMap<>();
    private Laboratorio atual;
    private boolean escuro = false;
    private boolean trabalhando = false;
    private JPanel raiz;
    private final Set<JPanel> paineisFundo = new HashSet<>();
    private JPanel blocoTabela;
    private JPanel[] cartoes;
    private final List<JLabel> titulosCartoes = new ArrayList<>();

    private ValidadorLaboratorios(Leitura leitura) {
        super("ValidadorLaboratorios");
        this.leitura = leitura;
        setDefaultCloseOperation(EXIT_ON_CLOSE);
        setMinimumSize(new Dimension(900, 640));
        setSize(1060, 760);
        setLocationRelativeTo(null);
        construir();
        aplicarTema();
        setVisible(true);
    }
    private static JPanel painel(LayoutManager layout) { JPanel p = new JPanel(layout); p.setOpaque(true); return p; }
    private static JLabel rotulo(String texto, int tamanho, boolean negrito) {
        JLabel l = new JLabel(texto); l.setFont(new Font("Segoe UI", negrito ? Font.BOLD : Font.PLAIN, tamanho)); return l;
    }
    private JPanel cartao(String texto, JLabel valor) {
        JPanel p = painel(new BorderLayout(4, 6)); p.setPreferredSize(new Dimension(200, 112));
        JLabel legenda = rotulo(texto.toUpperCase(Locale.ROOT), 11, true);
        titulosCartoes.add(legenda);
        p.add(legenda, BorderLayout.NORTH);
        valor.setFont(new Font("Segoe UI", Font.BOLD, valor == ip ? 15 : 18));
        p.add(valor, BorderLayout.CENTER);
        if (valor == ip) {
            JPanel acoes = painel(new FlowLayout(FlowLayout.RIGHT, 0, 0));
            acoes.add(copiar); p.add(acoes, BorderLayout.SOUTH);
        }
        return p;
    }
    private void construir() {
        raiz = painel(new BorderLayout(0, 16)); raiz.setBorder(BorderFactory.createEmptyBorder(22, 26, 18, 26)); setContentPane(raiz);
        JPanel cima = painel(new BorderLayout(0, 16)); raiz.add(cima, BorderLayout.NORTH);
        paineisFundo.add(raiz); paineisFundo.add(cima);
        JPanel cabecalho = painel(new BorderLayout()); cima.add(cabecalho, BorderLayout.NORTH);
        JPanel textos = painel(new GridLayout(3, 1, 0, 2));
        textos.add(rotulo("OPERAÇÕES DE TI", 11, true)); titulo.setFont(new Font("Segoe UI", Font.BOLD, 23)); textos.add(titulo);
        textos.add(rotulo("Valide softwares essenciais, driver de vídeo e ativação do Windows.", 12, false));
        cabecalho.add(textos, BorderLayout.CENTER);
        JPanel direita = painel(new FlowLayout(FlowLayout.RIGHT, 12, 12));
        JPanel identificacao = painel(new BorderLayout(0, 2));
        identificacao.add(rotulo("DISPOSITIVO", 10, true), BorderLayout.NORTH);
        identificacao.add(dispositivo, BorderLayout.CENTER);
        direita.add(identificacao); direita.add(tema); cabecalho.add(direita, BorderLayout.EAST);
        JPanel escolha = painel(new BorderLayout(12, 8)); escolha.setBorder(BorderFactory.createEmptyBorder(12, 16, 12, 16));
        escolha.add(rotulo("LABORATÓRIO", 11, true), BorderLayout.WEST);
        JPanel selecionar = painel(new BorderLayout(0, 5)); selecionar.add(seletor, BorderLayout.NORTH); selecionar.add(descricao, BorderLayout.SOUTH);
        seletor.setFont(new Font("Segoe UI", Font.BOLD, 13));
        seletor.setPreferredSize(new Dimension(300, 34));
        escolha.add(selecionar, BorderLayout.CENTER); cima.add(escolha, BorderLayout.CENTER);
        seletor.addItem("Selecione um laboratório..."); for (Laboratorio lab : leitura.laboratorios()) seletor.addItem(lab.nome());
        seletor.addActionListener(e -> selecionar());
        if (!leitura.avisos().isEmpty()) {
            JPanel aviso = painel(new BorderLayout());
            aviso.add(rotulo("⚠ " + leitura.avisos().size() + " configuração(ões) ignorada(s)", 12, true), BorderLayout.CENTER);
            JButton detalhes = new JButton("Ver detalhes"); detalhes.addActionListener(e -> JOptionPane.showMessageDialog(this, String.join("\n", leitura.avisos()), "Configurações ignoradas", JOptionPane.WARNING_MESSAGE));
            aviso.add(detalhes, BorderLayout.EAST); cima.add(aviso, BorderLayout.SOUTH);
        }
        JPanel meio = painel(new BorderLayout(0, 16)); raiz.add(meio, BorderLayout.CENTER);
        JPanel resumo = painel(new GridLayout(1, 4, 10, 0)); meio.add(resumo, BorderLayout.NORTH);
        paineisFundo.add(meio); paineisFundo.add(resumo);
        cartoes = new JPanel[]{cartao("Status geral", geral), cartao("Conformes", conformes), cartao("Não conformes", falhas), cartao("IPv4 do dispositivo", ip)};
        for (JPanel p : cartoes) resumo.add(p);
        blocoTabela = painel(new BorderLayout(0, 12)); meio.add(blocoTabela, BorderLayout.CENTER);
        JPanel barra = painel(new BorderLayout()); JPanel nome = painel(new FlowLayout(FlowLayout.LEFT, 8, 0));
        nome.add(rotulo("Itens monitorados", 16, true)); nome.add(quantidade); barra.add(nome, BorderLayout.WEST);
        barra.add(validar, BorderLayout.EAST); blocoTabela.add(barra, BorderLayout.NORTH);
        tabela.setRowHeight(38); tabela.setFillsViewportHeight(true); tabela.setSelectionMode(ListSelectionModel.SINGLE_SELECTION);
        tabela.setShowGrid(false); tabela.setIntercellSpacing(new Dimension(0, 0));
        tabela.setFont(new Font("Segoe UI", Font.PLAIN, 12));
        tabela.getTableHeader().setFont(new Font("Segoe UI", Font.BOLD, 11));
        tabela.getTableHeader().setPreferredSize(new Dimension(0, 38));
        tabela.setDefaultRenderer(Object.class, new DefaultTableCellRenderer() {
            @Override
            public Component getTableCellRendererComponent(JTable table, Object value, boolean selected, boolean focused, int row, int column) {
                JLabel cell = (JLabel) super.getTableCellRendererComponent(table, value, selected, focused, row, column);
                String status = Objects.toString(table.getValueAt(row, 3), "");
                Color texto = cor(escuro ? "#F5F7FA" : "#172033");
                Color corStatus = cor(escuro ? "#A8B3C5" : "#667085");
                Color fundo = cor(escuro ? (row % 2 == 0 ? "#151E2F" : "#1A263A") : (row % 2 == 0 ? "#FFFFFF" : "#F8FAFC"));
                if (status.contains("Conforme")) {
                    corStatus = cor(escuro ? "#47CD89" : "#087F4F");
                    if (column == 3) fundo = cor(escuro ? "#173D31" : "#ECFDF3");
                } else if (status.contains("Não encontrado")) {
                    corStatus = cor(escuro ? "#FF766F" : "#B42318");
                    if (column == 3) fundo = cor(escuro ? "#482523" : "#FEF3F2");
                } else if (status.contains("Não verificado")) {
                    corStatus = cor(escuro ? "#FDB022" : "#B54708");
                    if (column == 3) fundo = cor(escuro ? "#493817" : "#FFFAEB");
                } else if (status.contains("Verificando")) {
                    corStatus = cor(escuro ? "#76A3FF" : "#155EEF");
                    if (column == 3) fundo = cor(escuro ? "#1B315E" : "#E8F0FF");
                }
                cell.setBackground(selected ? cor(escuro ? "#254579" : "#DCEAFF") : fundo);
                cell.setForeground(column == 3 ? corStatus : texto);
                cell.setBorder(BorderFactory.createEmptyBorder(0, 10, 0, 10));
                cell.setToolTipText(Objects.toString(value, ""));
                return cell;
            }
        });
        tabela.getColumnModel().getColumn(0).setPreferredWidth(220); tabela.getColumnModel().getColumn(1).setPreferredWidth(135);
        tabela.getColumnModel().getColumn(2).setPreferredWidth(390); tabela.getColumnModel().getColumn(3).setPreferredWidth(145);
        JScrollPane scroll = new JScrollPane(tabela); scroll.setBorder(BorderFactory.createEmptyBorder()); blocoTabela.add(scroll, BorderLayout.CENTER);
        JPanel rodape = painel(new FlowLayout(FlowLayout.RIGHT)); rodape.add(ultima); raiz.add(rodape, BorderLayout.SOUTH); paineisFundo.add(rodape);
        validar.setEnabled(false); validar.addActionListener(e -> validar());
        tema.addActionListener(e -> { escuro = !escuro; aplicarTema(); });
        copiar.addActionListener(e -> {
            if (ip.getText().equals("Não encontrado")) return;
            Toolkit.getDefaultToolkit().getSystemClipboard().setContents(new java.awt.datatransfer.StringSelection(ip.getText()), null);
            copiar.setText("Copiado"); new javax.swing.Timer(1600, event -> { copiar.setText("Copiar"); ((javax.swing.Timer)event.getSource()).stop(); }).start();
        });
        getRootPane().getInputMap(JComponent.WHEN_IN_FOCUSED_WINDOW).put(KeyStroke.getKeyStroke("F5"), "validar");
        getRootPane().getActionMap().put("validar", new AbstractAction(){@Override public void actionPerformed(java.awt.event.ActionEvent e){validar();}});
    }
    private List<Software> itens() {
        List<Software> lista = new ArrayList<>(); lista.add(VIDEO); lista.add(ATIVACAO);
        if (atual != null) lista.addAll(atual.softwares()); return lista;
    }
    private void selecionar() {
        if (trabalhando) return;
        String nome = (String)seletor.getSelectedItem();
        atual = leitura.laboratorios().stream().filter(x -> x.nome().equals(nome)).findFirst().orElse(null);
        if (atual == null) { validar.setEnabled(false); descricao.setText("Escolha um laboratório para iniciar"); quantidade.setText("Selecione um ambiente"); ultima.setText("Última verificação: selecione um laboratório"); }
        else { validar.setEnabled(true); descricao.setText(atual.descricao() + " • " + itens().size() + " itens monitorados");
            descricao.setToolTipText(atual.descricao());
            ultima.setText("Última verificação: " + ultimas.getOrDefault(atual.codigo(), "ainda não realizada")); }
        atualizarTabela(); atualizarResumo();
    }
    private void atualizarTabela() {
        modelo.setRowCount(0); if (atual == null) { modelo.addRow(new Object[]{"Selecione um laboratório", "—", "Os itens monitorados serão exibidos após a seleção.", "○ Aguardando"}); return; }
        Map<String, Resultado> mapa = resultados.getOrDefault(atual.codigo(), Map.of());
        for (Software s : itens()) {
            Resultado r = mapa.getOrDefault(s.nome(), new Resultado("pendente", ""));
            modelo.addRow(new Object[]{s.nome(), s.categoria(), r.detalhe().isBlank() ? s.caminhos().get(0) : r.detalhe(), textoStatus(r.estado())});
        }
    }
    private static String textoStatus(String s) { return switch(s) {case "conforme" -> "✓ Conforme"; case "falha" -> "× Não encontrado"; case "erro" -> "⚠ Não verificado"; case "verificando" -> "◌ Verificando"; default -> "○ Pendente";}; }
    private void atualizarResumo() {
        if (atual == null) { geral.setText("Selecione"); conformes.setText("—"); falhas.setText("—"); quantidade.setText("Selecione um ambiente"); atualizarCoresResumo(); return; }
        Collection<Resultado> vals = resultados.getOrDefault(atual.codigo(), Map.of()).values();
        long ok = vals.stream().filter(r -> r.estado().equals("conforme")).count();
        long nao = vals.stream().filter(r -> r.estado().equals("falha") || r.estado().equals("erro")).count();
        conformes.setText(ok + " de " + itens().size()); falhas.setText("" + nao);
        long verificados = ok + nao;
        quantidade.setText(verificados == 0 && !trabalhando ? itens().size() + " itens" :
            verificados + " de " + itens().size() + " verificados");
        geral.setText(trabalhando ? "Verificando" : ok + nao == 0 ? "Aguardando" : nao == 0 && ok == itens().size() ? "Em conformidade" : "Requer atenção");
        atualizarCoresResumo();
    }
    private void atualizarCoresResumo() {
        Color texto = cor(escuro ? "#F5F7FA" : "#172033");
        Color azul = cor(escuro ? "#4C85FF" : "#155EEF");
        Color verde = cor(escuro ? "#47CD89" : "#079455");
        Color vermelho = cor(escuro ? "#FF766F" : "#D92D20");
        conformes.setForeground(conformes.getText().equals("—") ? texto : verde);
        falhas.setForeground(falhas.getText().equals("0") || falhas.getText().equals("—") ? texto : vermelho);
        geral.setForeground(geral.getText().equals("Em conformidade") ? verde : geral.getText().equals("Requer atenção") ? vermelho : azul);
    }
    private void validar() {
        if (atual == null || trabalhando) return;
        trabalhando = true; validar.setEnabled(false); seletor.setEnabled(false); validar.setText("Validando...");
        String codigo = atual.codigo(); Map<String, Resultado> mapa = resultados.computeIfAbsent(codigo, x -> new LinkedHashMap<>());
        for (Software s : itens()) mapa.put(s.nome(), new Resultado("verificando", "")); atualizarTabela(); atualizarResumo();
        new SwingWorker<Void, Map.Entry<String, Resultado>>() {
            @Override
            protected Void doInBackground() {
                for (Software s : itens()) {
                    Resultado r = s == VIDEO ? verificarVideo() : s == ATIVACAO ? verificarAtivacao() : verificarSoftware(s);
                    publish(Map.entry(s.nome(), r));
                } return null;
            }
            @Override
            protected void process(List<Map.Entry<String, Resultado>> entradas) {
                for (var e : entradas) mapa.put(e.getKey(), e.getValue()); atualizarTabela(); atualizarResumo();
            }
            @Override
            protected void done() {
                trabalhando = false; validar.setText("Validar novamente"); validar.setEnabled(true); seletor.setEnabled(true);
                String data = LocalDateTime.now().format(DateTimeFormatter.ofPattern("dd/MM/yyyy 'às' HH:mm:ss"));
                ultimas.put(codigo, data); ultima.setText("Última verificação: " + data); atualizarResumo();
            }
        }.execute();
    }
    private void aplicarTema() {
        Color fundo = cor(escuro ? "#0D1424" : "#F3F6FA"), superficie = cor(escuro ? "#151E2F" : "#FFFFFF");
        Color texto = cor(escuro ? "#F5F7FA" : "#172033"), azul = cor(escuro ? "#4C85FF" : "#155EEF");
        pintar(raiz, fundo, superficie, texto);
        Color borda = cor(escuro ? "#2A3950" : "#DCE3EC");
        Color[] destaques = {azul, cor(escuro ? "#47CD89" : "#079455"), cor(escuro ? "#FF766F" : "#D92D20"), azul};
        for (int i = 0; i < cartoes.length; i++) {
            cartoes[i].setBorder(BorderFactory.createCompoundBorder(BorderFactory.createLineBorder(borda, 1, true),
                BorderFactory.createCompoundBorder(BorderFactory.createMatteBorder(0, 4, 0, 0, destaques[i]), BorderFactory.createEmptyBorder(12, 14, 12, 14))));
        }
        blocoTabela.setBorder(BorderFactory.createCompoundBorder(BorderFactory.createLineBorder(borda, 1, true), BorderFactory.createEmptyBorder(16, 16, 14, 16)));
        titulo.setForeground(azul); tema.setText(escuro ? "☀  Tema claro" : "☾  Tema escuro");
        for (JLabel legenda : titulosCartoes) legenda.setForeground(cor(escuro ? "#A8B3C5" : "#667085"));
        dispositivo.setForeground(azul);
        descricao.setForeground(cor(escuro ? "#A8B3C5" : "#667085"));
        atualizarCoresResumo();
        ip.setForeground(azul);
        tabela.setBackground(superficie); tabela.setForeground(texto);
        tabela.getTableHeader().setBackground(cor(escuro ? "#1A263A" : "#F8FAFC")); tabela.getTableHeader().setForeground(texto);
        validar.setUI(new javax.swing.plaf.basic.BasicButtonUI());
        validar.setBackground(azul); validar.setForeground(Color.WHITE); validar.setFocusPainted(false);
        validar.setBorder(BorderFactory.createEmptyBorder(10, 18, 10, 18));
        copiar.setUI(new javax.swing.plaf.basic.BasicButtonUI()); copiar.setBackground(cor(escuro ? "#1B315E" : "#E8F0FF"));
        copiar.setForeground(azul); copiar.setFont(new Font("Segoe UI", Font.BOLD, 10)); copiar.setFocusPainted(false);
        copiar.setBorder(BorderFactory.createEmptyBorder(4, 8, 4, 8));
        tema.setUI(new javax.swing.plaf.basic.BasicButtonUI()); tema.setBackground(cor(escuro ? "#243146" : "#E8F0FF"));
        tema.setForeground(azul); tema.setFocusPainted(false); tema.setBorder(BorderFactory.createEmptyBorder(9, 12, 9, 12));
        quantidade.setForeground(azul); ultima.setForeground(cor(escuro ? "#A8B3C5" : "#667085"));
        tabela.repaint(); revalidate();
        repaint();
    }
    private static Color cor(String hex) { return Color.decode(hex); }
    private void pintar(Component c, Color fundo, Color superficie, Color texto) {
        if (c instanceof JPanel p) p.setBackground(paineisFundo.contains(p) ? fundo : superficie);
        if (c instanceof JLabel l) l.setForeground(texto);
        if (c instanceof Container cont) for (Component filho : cont.getComponents()) pintar(filho, fundo, superficie, texto);
    }
    private static Resultado verificarSoftware(Software s) {
        for (String original : s.caminhos()) {
            String caminho = expandir(original);
            try {
                if (Files.exists(Path.of(caminho))) return new Resultado("conforme", caminho);
                if (caminho.indexOf('*') >= 0 || caminho.indexOf('?') >= 0) {
                    Path p = Path.of(caminho);
                    // PathMatcher glob abrange componentes intermediários, como QGIS *.
                    Path raiz = p.getRoot(); Path inicio = raiz == null ? Path.of(".") : raiz;
                    int primeira = -1; for (int i=0; i<p.getNameCount(); i++) if (p.getName(i).toString().matches(".*[\\*\\?].*")) { primeira=i; break; }
                    for (int i=0; i<primeira; i++) inicio=inicio.resolve(p.getName(i));
                    if (primeira >= 0 && Files.isDirectory(inicio)) {
                        String padrao = p.subpath(primeira, p.getNameCount()).toString().replace('\\', '/');
                        PathMatcher matcher = FileSystems.getDefault().getPathMatcher("glob:" + padrao);
                        Path base = inicio;
                        try (var stream = Files.walk(base, Math.max(1, p.getNameCount()-primeira))) {
                            Optional<Path> achado = stream.filter(Files::exists).filter(x -> matcher.matches(base.relativize(x))).findFirst();
                            if (achado.isPresent()) return new Resultado("conforme", achado.get().toString());
                        }
                    }
                }
            } catch (IOException | RuntimeException ignored) { }
        }
        return new Resultado("falha", "");
    }
    private static String expandir(String s) {
        String out = s.replaceFirst("^~(?=[/\\\\]|$)", Matcher.quoteReplacement(System.getProperty("user.home")));
        for (var env : System.getenv().entrySet()) out = out.replaceAll("(?i)%" + Pattern.quote(env.getKey()) + "%", Matcher.quoteReplacement(env.getValue()));
        return out;
    }
    private static boolean windows() { return System.getProperty("os.name", "").toLowerCase(Locale.ROOT).contains("win"); }
    private static String normal(String s) { return Normalizer.normalize(s, Normalizer.Form.NFD).replaceAll("\\p{M}", "").toLowerCase(Locale.ROOT); }
    private static List<Map<String,Object>> objetos(Object json) {
        List<Map<String,Object>> saida = new ArrayList<>(); if (json instanceof Map<?,?> m) saida.add(mapa(m));
        if (json instanceof List<?> lista) for (Object item : lista) if (item instanceof Map<?,?> m) saida.add(mapa(m)); return saida;
    }
    private static String valor(Map<String,Object> m, String chave) { return Objects.toString(m.get(chave), "").trim(); }
    private static int numero(Object x, int padrao) { try { return Integer.parseInt(Objects.toString(x)); } catch (NumberFormatException e) { return padrao; } }
    private static Resultado verificarVideo() {
        if (!windows()) return new Resultado("erro", "Verificação disponível somente no Windows");
        try {
            String comando = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $ErrorActionPreference='Stop'; " +
                "$a=@(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,ConfigManagerErrorCode,InfFilename); ConvertTo-Json -InputObject $a -Compress -Depth 3";
            List<Map<String,Object>> adaptadores = objetos(Json.parse(powershell(comando,20)));
            if (adaptadores.isEmpty()) return new Resultado("falha", "Nenhum adaptador de vídeo foi identificado");
            List<String> ok = new ArrayList<>(), problemas = new ArrayList<>();
            for (var a : adaptadores) {
                String nome = valor(a,"Name"), versao = valor(a,"DriverVersion");
                String id = normal(nome + " " + valor(a,"InfFilename"));
                if (id.contains("microsoft basic display adapter") || id.contains("adaptador de video basico da microsoft") || id.contains("adaptador basico de video da microsoft") || id.contains("basicdisplay.inf")) problemas.add(nome + " — driver do fabricante ausente");
                else if (numero(a.get("ConfigManagerErrorCode"),0)!=0) problemas.add(nome + " — erro do dispositivo (código " + a.get("ConfigManagerErrorCode") + ")");
                else if (versao.isBlank()) problemas.add(nome + " — versão do driver não identificada");
                else ok.add(nome + " — versão " + versao);
            }
            if (!problemas.isEmpty()) return new Resultado("falha", String.join("; ", problemas));
            return new Resultado("conforme", String.join("; ", ok));
        } catch (IOException | InterruptedException | IllegalArgumentException e) { return new Resultado("erro", "Não foi possível consultar o driver de vídeo"); }
    }
    private static Resultado verificarAtivacao() {
        if (!windows()) return new Resultado("erro", "Verificação disponível somente no Windows");
        try {
            String cmd = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $ErrorActionPreference='Stop'; " +
                "$p=@(Get-CimInstance -Namespace root/cimv2 -ClassName SoftwareLicensingProduct -Filter \"ApplicationID='55c92734-d682-4d71-983e-d6ec3f16059f' AND PartialProductKey IS NOT NULL\" | Select-Object Name,Description,LicenseStatus,GracePeriodRemaining); ConvertTo-Json -InputObject $p -Compress -Depth 3";
            List<Map<String,Object>> produtos = objetos(Json.parse(powershell(cmd,20)));
            if (produtos.isEmpty()) return ativacaoSlmgr();
            for (var p : produtos) if (numero(p.get("LicenseStatus"),-1)==1)
                return new Resultado("conforme", valor(p,"Name") + " — Ativado" + (normal(valor(p,"Description")).contains("kmsclient") ? " — KMS" : ""));
            int estado = -1; for (var p : produtos) { int n=numero(p.get("LicenseStatus"),-1); if (n>=0 && n<=6) {estado=n;break;} }
            String[] estados = {"Windows não licenciado", "Windows ativado", "Windows em período de tolerância inicial", "Windows em período de tolerância adicional", "Windows em período de tolerância por licença não genuína", "Windows em modo de notificação", "Windows em período de tolerância estendido"};
            return new Resultado("falha", estado<0 ? "Windows não ativado ou estado da licença desconhecido" : estados[estado]);
        } catch (IOException | InterruptedException | IllegalArgumentException e) { return ativacaoSlmgr(); }
    }
    private static Resultado ativacaoSlmgr() {
        try {
            String cmd = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $ErrorActionPreference='Stop'; $saida=@(& \"$env:SystemRoot\\System32\\cscript.exe\" //Nologo \"$env:SystemRoot\\System32\\slmgr.vbs\" /dli 2>&1); $r=[PSCustomObject]@{ExitCode=$LASTEXITCODE; Output=($saida -join \"`n\")}; ConvertTo-Json -InputObject $r -Compress";
            Map<String,Object> r = mapa((Map<?,?>)Json.parse(powershell(cmd,25)));
            if (numero(r.get("ExitCode"),-1)!=0) throw new IOException("SLMGR falhou");
            String saida=normal(valor(r,"Output"));
            for (String s : List.of("unlicensed", "nao licenciado", "notification", "notificacao", "not activated", "nao ativado", "grace", "tolerancia")) if (saida.contains(s)) return new Resultado("falha", "Windows não ativado ou em período de tolerância");
            for (String s : List.of("license status: licensed", "status da licenca: licenciado", "estado da licenca: licenciado", "permanently activated", "permanentemente ativado", "permanentemente ativada")) if (saida.contains(s)) return new Resultado("conforme", "Windows ativado — verificado pelo SLMGR");
            return new Resultado("erro", "Estado da ativação retornado pelo Windows não foi reconhecido");
        } catch (IOException | InterruptedException | IllegalArgumentException | ClassCastException e) { return new Resultado("erro", "Não foi possível consultar a ativação do Windows"); }
    }
    private static String powershell(String script, int segundos) throws IOException, InterruptedException {
        Process p = new ProcessBuilder("powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script).redirectErrorStream(true).start();
        boolean terminou = p.waitFor(segundos, TimeUnit.SECONDS); if (!terminou) { p.destroyForcibly(); throw new IOException("Tempo esgotado"); }
        String resposta = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8).replaceFirst("^\\uFEFF", "").trim();
        if (p.exitValue()!=0 || resposta.isBlank()) throw new IOException("Falha PowerShell"); return resposta;
    }
    private static String host() { try {return InetAddress.getLocalHost().getHostName();} catch (UnknownHostException e){return "LOCAL";} }
    private static String ipPrincipal() {
        try {
            List<NetworkInterface> interfaces = Collections.list(NetworkInterface.getNetworkInterfaces());
            interfaces.sort(Comparator.comparingInt(n -> normal(n.getDisplayName()).matches(".*(virtual|vmware|vbox|hyper-v|vethernet|loopback|docker|wsl).*") ? 1 : 0));
            for (NetworkInterface n : interfaces) if (n.isUp() && !n.isLoopback()) for (InetAddress a : Collections.list(n.getInetAddresses()))
                if (a instanceof Inet4Address && !a.isLoopbackAddress() && !a.isLinkLocalAddress()) return a.getHostAddress();
        } catch (SocketException | SecurityException ignored) { } return "Não encontrado";
    }
    private static Map<String,Object> mapa(Map<?,?> objeto) {
        Map<String,Object> saida = new LinkedHashMap<>(); for (var e : objeto.entrySet()) saida.put(String.valueOf(e.getKey()), e.getValue()); return saida;
    }
    private static String campo(Map<String,Object> m, String chave) {
        Object o=m.get(chave); if (!(o instanceof String s) || s.isBlank()) throw new IllegalArgumentException("o campo '" + chave + "' deve conter um texto"); return s.trim();
    }
    private static Laboratorio carregar(String conteudo) {
        Object parsed=Json.parse(conteudo.replaceFirst("^\\uFEFF", "")); if (!(parsed instanceof Map<?,?> dados)) throw new IllegalArgumentException("a raiz deve ser um objeto");
        Map<String,Object> m=mapa(dados); String codigo=campo(m,"codigo"), lab=campo(m,"laboratorio");
        String desc=Objects.toString(m.getOrDefault("descricao", ""));
        if (!(m.getOrDefault("ordem",0) instanceof Number)) throw new IllegalArgumentException("ordem deve ser um inteiro");
        if (!(m.get("softwares") instanceof List<?> itens)) throw new IllegalArgumentException("softwares deve ser uma lista");
        List<Software> softwares=new ArrayList<>(); Set<String> vistos=new HashSet<>();
        for (Object item : itens) {
            if (!(item instanceof Map<?,?> d)) throw new IllegalArgumentException("um software não é objeto");
            Map<String,Object> s=mapa(d); Object ativo=s.getOrDefault("ativo", true);
            if (!(ativo instanceof Boolean)) throw new IllegalArgumentException("ativo deve ser true ou false"); if (Boolean.FALSE.equals(ativo)) continue;
            String sn=campo(s,"nome"), cat=campo(s,"categoria");
            if (sn.equalsIgnoreCase(VIDEO.nome()) || sn.equalsIgnoreCase(ATIVACAO.nome()) || !vistos.add(sn.toLowerCase(Locale.ROOT))) throw new IllegalArgumentException("software duplicado ou reservado: " + sn);
            if (!(s.get("caminhos") instanceof List<?> lista) || lista.isEmpty()) throw new IllegalArgumentException(sn + ": caminhos deve ser lista não vazia");
            List<String> caminhos=new ArrayList<>(); for(Object c:lista) if (c instanceof String valor && !valor.isBlank()) caminhos.add(valor.trim()); else throw new IllegalArgumentException(sn + ": caminho inválido");
            softwares.add(new Software(sn,cat,caminhos));
        }
        if (softwares.isEmpty()) throw new IllegalArgumentException("nenhum software ativo");
        return new Laboratorio(codigo,lab,desc,softwares);
    }
    private static Path pastaAplicacao() {
        try { Path origem=Path.of(ValidadorLaboratorios.class.getProtectionDomain().getCodeSource().getLocation().toURI());
            return Files.isRegularFile(origem) ? origem.getParent() : Path.of("").toAbsolutePath(); }
        catch (URISyntaxException | IllegalArgumentException | SecurityException e) { return Path.of("").toAbsolutePath(); }
    }
    private static Leitura configuracoes() throws IOException {
        Map<String,String> arquivos=new TreeMap<>(String.CASE_INSENSITIVE_ORDER);
        try (InputStream arquivo=ValidadorLaboratorios.class.getProtectionDomain().getCodeSource().getLocation().openStream()) {
            // Arquivos no JAR servem de base; JSON externo com o mesmo nome tem prioridade.
            try (JarInputStream jar=new JarInputStream(arquivo)) {
                JarEntry e; while ((e=jar.getNextJarEntry())!=null) if (e.getName().startsWith("configuracoes/") && e.getName().endsWith(".json")) {
                    arquivos.put(Path.of(e.getName()).getFileName().toString(), new String(jar.readAllBytes(),StandardCharsets.UTF_8));
                }
            }
        } catch (IOException | IllegalArgumentException ignored) { /* Em execução pelo código-fonte, usar apenas JSONs externos. */ }
        Path externa=pastaAplicacao().resolve("configuracoes");
        if (!Files.isDirectory(externa)) externa=Path.of("configuracoes");
        // O Code Runner do VS Code executa dentro de src; os perfis ficam no projeto.
        if (!Files.isDirectory(externa) && Files.exists(Path.of("ValidadorLaboratorios.java")))
            externa=Path.of("..", "configuracoes");
        if (Files.isDirectory(externa)) try(var stream=Files.list(externa)) {
            for (Path p : stream.filter(x -> x.getFileName().toString().toLowerCase(Locale.ROOT).endsWith(".json")).toList())
                arquivos.put(p.getFileName().toString(), Files.readString(p,StandardCharsets.UTF_8));
        }
        if (arquivos.isEmpty()) throw new IOException("Nenhum JSON encontrado na pasta configuracoes nem no JAR.");
        List<Laboratorio> labs=new ArrayList<>(); List<String> avisos=new ArrayList<>(); Set<String> codigos=new HashSet<>(), nomes=new HashSet<>();
        for(var e:arquivos.entrySet()) try {
            Laboratorio lab=carregar(e.getValue());
            if(!codigos.add(lab.codigo().toLowerCase(Locale.ROOT)) || !nomes.add(lab.nome().toLowerCase(Locale.ROOT))) throw new IllegalArgumentException("código ou laboratório duplicado");
            labs.add(lab);
        } catch (RuntimeException x) { avisos.add(e.getKey()+": "+x.getMessage()); }
        if(labs.isEmpty()) throw new IOException("Nenhuma configuração válida.\n"+String.join("\n",avisos));
        labs.sort(Comparator.comparing(x -> normal(x.nome()), (a,b) -> {
            Matcher m1=Pattern.compile("\\d+|\\D+").matcher(a), m2=Pattern.compile("\\d+|\\D+").matcher(b);
            while(m1.find() && m2.find()){String s=m1.group(),t=m2.group();int c=s.matches("\\d+") && t.matches("\\d+") ? Long.compare(Long.parseLong(s),Long.parseLong(t)) : s.compareTo(t);if(c!=0)return c;}
            return a.compareTo(b);
        }));
        return new Leitura(labs,avisos);
    }
    public static void main(String[] args) {
        try { Leitura labs=configuracoes();
            if (args.length>0 && args[0].equals("--check-config")) {System.out.println("Configurações válidas: "+labs.laboratorios().size()); for(String aviso:labs.avisos())System.err.println(aviso);return;}
            SwingUtilities.invokeLater(() -> new ValidadorLaboratorios(labs));
        } catch(IOException | IllegalArgumentException e) { if(args.length>0 && args[0].equals("--check-config")){System.err.println(e.getMessage());System.exit(1);} else JOptionPane.showMessageDialog(null,e.getMessage(),"Configuração inválida",JOptionPane.ERROR_MESSAGE); }
    }
    /** Parser JSON mínimo para os perfis e respostas CIM. */
    private static final class Json {
        private final String src; private int pos;
        private Json(String src){this.src=src;}
        static Object parse(String src){Json p=new Json(src);Object val=p.valor();p.ws();if(p.pos!=src.length())throw p.erro("conteúdo após o JSON");return val;}
        private IllegalArgumentException erro(String s){return new IllegalArgumentException(s+" na posição "+pos);}
        private void ws(){while(pos<src.length()&&Character.isWhitespace(src.charAt(pos)))pos++;}
        private char proximo(){if(pos>=src.length())throw erro("fim inesperado");return src.charAt(pos++);}
        private Object valor(){ws();char c=proximo();return switch(c){case '{'->objeto();case '['->lista();case '"'->texto();case 't'->literal("rue",true);case 'f'->literal("alse",false);case 'n'->literal("ull",null);default->{if(c=='-'||Character.isDigit(c)){pos--;yield numero();}throw erro("valor inválido");}};}
        private Object literal(String fim,Object valor){for(char c:fim.toCharArray())if(proximo()!=c)throw erro("literal inválido");return valor;}
        private Map<String,Object> objeto(){Map<String,Object> m=new LinkedHashMap<>();ws();if(src.charAt(pos)=='}'){pos++;return m;}while(true){ws();if(proximo()!='"')throw erro("chave esperada");String chave=texto();ws();if(proximo()!=':')throw erro(": esperado");m.put(chave,valor());ws();char c=proximo();if(c=='}')return m;if(c!=',')throw erro("vírgula esperada");}}
        private List<Object> lista(){List<Object> a=new ArrayList<>();ws();if(src.charAt(pos)==']'){pos++;return a;}while(true){a.add(valor());ws();char c=proximo();if(c==']')return a;if(c!=',')throw erro("vírgula esperada");}}
        private String texto(){StringBuilder s=new StringBuilder();while(true){char c=proximo();if(c=='"')return s.toString();if(c<32)throw erro("controle inválido");if(c!='\\'){s.append(c);continue;}char e=proximo();switch(e){case '"','\\','/'->s.append(e);case 'b'->s.append('\b');case 'f'->s.append('\f');case 'n'->s.append('\n');case 'r'->s.append('\r');case 't'->s.append('\t');case 'u'->{int n=0;for(int i=0;i<4;i++){int d=Character.digit(proximo(),16);if(d<0)throw erro("Unicode inválido");n=n*16+d;}s.append((char)n);}default->throw erro("escape inválido");}}}
        private Number numero(){int inicio=pos;if(src.charAt(pos)=='-')pos++;while(pos<src.length()&&Character.isDigit(src.charAt(pos)))pos++;if(pos<src.length()&&src.charAt(pos)=='.'){pos++;while(pos<src.length()&&Character.isDigit(src.charAt(pos)))pos++;}if(pos<src.length()&&(src.charAt(pos)=='e'||src.charAt(pos)=='E')){pos++;if(pos<src.length()&&(src.charAt(pos)=='+'||src.charAt(pos)=='-'))pos++;while(pos<src.length()&&Character.isDigit(src.charAt(pos)))pos++;}try{return Double.valueOf(src.substring(inicio,pos));}catch(NumberFormatException e){throw erro("número inválido");}}
    }
}
