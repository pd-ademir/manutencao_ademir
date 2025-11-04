document.addEventListener('DOMContentLoaded', function () {
    // Pega os elementos do DOM
    const filialSelect = document.getElementById('filial_filtro');
    const unidadeSelect = document.getElementById('unidade_filtro');

    // Só executa o script se o seletor de filial existir na página
    if (!filialSelect) {
        return;
    }

    // Pega os dados embutidos no HTML
    const filialUnidadeMap = JSON.parse(document.getElementById('filial-unidade-map-data').textContent);
    const todasUnidades = JSON.parse(document.getElementById('todas-unidades-data').textContent);
    const unidadeSelecionadaAtual = document.getElementById('unidade-selecionada-data').textContent.trim();

    function atualizarUnidades() {
        const filialSelecionada = filialSelect.value;
        
        // Limpa as opções atuais do select de unidade
        unidadeSelect.innerHTML = '<option value="">Todas as Unidades</option>';

        let unidadesParaMostrar = [];
        if (filialSelecionada && filialUnidadeMap[filialSelecionada]) {
            // Se uma filial específica for selecionada, usa as unidades do mapa
            unidadesParaMostrar = filialUnidadeMap[filialSelecionada];
        } else {
            // Se "Todas as Filiais" for selecionado, mostra todas as unidades disponíveis
            unidadesParaMostrar = todasUnidades;
        }

        // Popula o select de unidade com as opções corretas
        unidadesParaMostrar.forEach(function(unidade) {
            const option = document.createElement('option');
            option.value = unidade;
            option.textContent = unidade;
            // Se esta for a unidade que já estava selecionada, marca ela de novo
            if (unidade === unidadeSelecionadaAtual && filialSelect.value === document.getElementById('filial-selecionada-data').textContent.trim()) {
                option.selected = true;
            }
            unidadeSelect.appendChild(option);
        });
    }

    // Adiciona o listener para o evento de mudança no select de filial
    filialSelect.addEventListener('change', atualizarUnidades);

    // Chama a função uma vez no carregamento da página para garantir que o estado inicial do select de unidades esteja correto
    // especialmente quando o formulário é recarregado com uma filial já selecionada.
    atualizarUnidades();
});
