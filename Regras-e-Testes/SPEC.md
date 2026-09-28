# Rebscreen 0.2-beta — requisitos atuais

- Rebscreen é o nome do aplicativo, executável, janela, bandeja e dados novos em `%LOCALAPPDATA%\Rebscreen`.
- Na primeira execução, configurações Telinha são importadas apenas se Rebscreen ainda não possuir suas próprias; os arquivos Telinha não são apagados.
- Os temas disponíveis são `Rebel` (padrão), `Painel Técnico` e `Cassette Futurism`. Aplicar um preset instala seus perfis Vertical e Horizontal; demais opções não substituem layouts salvos.
- O inglês é o idioma padrão. A interface e os textos dos três temas podem ser selecionados em inglês, português do Brasil, espanhol, italiano, russo e chinês simplificado; preferências antigas recebem inglês sem perder outras configurações.
- O campo curto About do GitHub não tem seletor interativo. O README fornece navegação para as seis descrições completas.
- O Painel Técnico tem cabeçalhos Rebscreen com hora/data, monitor técnico e Player com capa circular, fonte e ícone vetorial local quando identificável.
- Os ícones de fonte são desenhados nativamente em Pillow; nenhum logotipo externo foi baixado.
- CPU, GPU e RAM só podem gerar alertas quando vierem de uma fonte real identificada. Enquanto forem amostras, a interface e a tela devem mostrar que são demonstração.
- Envio USB automático é opcional, desligado por padrão e nunca deve usar cadência inferior a 30 segundos. Não alterar firmware ou protocolo sem autorização explícita.
- O botão `Como resolver` aparece quando uma dependência opcional está indisponível. Ele salva um guia TXT UTF-8 no idioma atual e não instala pacotes nem repete consultas de sensores.
