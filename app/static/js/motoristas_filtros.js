document.addEventListener('DOMContentLoaded', function () {
    const filialSelect = document.getElementById('filial_filtro');
    if (!filialSelect) return;

    const unidadeSelect = document.getElementById('unidade_filtro');
    
    const filialUnidadeMap = JSON.parse(document.getElementById('filial-unidade-map-data').textContent);
    const todasUnidades = JSON.parse(document.getElementById('todas-unidades-data').textContent);
    const unidadeSelecionadaAtual = document.getElementById('unidade-selecionada-data').textContent.trim();

    function atualizarUnidades() {
        const filialSelecionada = filialSelect.value;
        unidadeSelect.innerHTML = '<option value="">Todas as Unidades</option>';

        let unidadesParaMostrar = (filialSelecionada && filialUnidadeMap[filialSelecionada]) 
                                    ? filialUnidadeMap[filialSelecionada] 
                                    : todasUnidades;

        unidadesParaMostrar.forEach(function(unidade) {
            const option = document.createElement('option');
            option.value = unidade;
            option.textContent = unidade;
            if (unidade === unidadeSelecionadaAtual && filialSelect.value === document.getElementById('filial-selecionada-data').textContent.trim()) {
                option.selected = true;
            }
            unidadeSelect.appendChild(option);
        });
    }

    filialSelect.addEventListener('change', atualizarUnidades);
    atualizarUnidades();
});
