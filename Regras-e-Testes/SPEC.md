# Rebscreen — requisitos atuais

- Rebscreen é o nome do aplicativo, executável, janela, bandeja e dados novos em `%LOCALAPPDATA%\Rebscreen`.
- Na primeira execução, configurações Telinha são importadas apenas se Rebscreen ainda não possuir suas próprias; os arquivos Telinha não são apagados.
- Os únicos temas são `Rebel` (padrão) e `Painel Técnico` (alternativo). Apenas `Aplicar tema e layout` instala seus perfis Vertical e Horizontal.
- O Painel Técnico tem cabeçalhos Rebscreen com hora/data, monitor técnico e Player com capa circular, fonte e ícone vetorial local quando identificável.
- Os ícones de fonte são desenhados nativamente em Pillow; nenhum logotipo externo foi baixado.
- CPU, GPU e RAM só podem gerar alertas quando vierem de uma fonte real identificada. Enquanto forem amostras, a interface e a tela devem mostrar que são demonstração.
- Envio USB automático é opcional, desligado por padrão e nunca deve usar cadência inferior a 30 segundos. Não alterar firmware ou protocolo sem autorização explícita.
