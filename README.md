# Simulador web — Carga acelerada e radiação eletromagnética

Esta é uma versão do seu simulador Pygame preparada para execução no navegador com **pygbag + pygame-ce**.

O código original foi preservado conceitualmente: carga, linhas retardadas, modos de movimento, arrastar com o mouse e os controles deslizantes continuam sendo a mesma simulação. A adaptação principal está no loop de execução.

## Arquivos

- `main.py` — simulador adaptado para a web.
- `requirements.txt` — dependências.
- `.github/workflows/pages.yml` — publica automaticamente o simulador no GitHub Pages.
- `COMO_PUBLICAR.md` — guia passo a passo para quem nunca fez isso.

## Como a adaptação funciona

O pygbag espera uma aplicação com `main.py` e um loop compatível com o modelo assíncrono do navegador. Por isso, o loop principal agora é `async` e usa `await asyncio.sleep(0)` em cada quadro.

O pygbag documenta que esse `await` devolve o controle ao loop do navegador/WebAssembly e que a aplicação deve ser organizada dessa maneira. O projeto também informa que o pygbag suporta pygame-ce, não o pacote pygame tradicional.

## Publicação automática

O workflow incluído usa GitHub Actions para:

1. instalar Python 3.11, pygbag e pygame-ce;
2. executar o build do pygbag;
3. localizar a página HTML gerada e transformá-la em `index.html`;
4. publicar `build/web` no GitHub Pages.

GitHub atualmente documenta `actions/checkout@v7`, `actions/setup-python@v7`, `actions/configure-pages@v5`, `actions/upload-pages-artifact@v4` e `actions/deploy-pages@v4` para esse tipo de implantação.

## Teste local

Em um computador com Python 3.11 ou 3.12:

```bash
python -m pip install --upgrade pygbag pygame-ce
python -m pygbag --build .
```

Para testar no servidor local do pygbag, use:

```bash
python -m pygbag .
```

e abra o endereço mostrado no terminal.

## Importante

Nesta sessão eu consegui adaptar e verificar a sintaxe do `main.py`, mas não consegui executar o build completo do pygbag neste ambiente porque a instalação de pacotes externos está sem acesso à rede. Portanto, a primeira execução no GitHub Actions será o teste efetivo de empacotamento WebAssembly.
