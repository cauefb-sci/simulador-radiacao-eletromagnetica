# Como colocar o simulador no Notion — passo a passo

Você não precisa saber programação web para fazer esta parte.

## 1. Crie um repositório no GitHub

No GitHub, crie um repositório novo, por exemplo:

`simulador-radiacao-eletromagnetica`

Pode deixá-lo público. Não é necessário adicionar README, `.gitignore` ou licença durante a criação, porque esta pasta já contém os arquivos necessários.

## 2. Envie os arquivos desta pasta

Envie **todo o conteúdo** desta pasta para o repositório, mantendo esta estrutura:

```text
main.py
requirements.txt
README.md
COMO_PUBLICAR.md
.github/
  workflows/
    pages.yml
```

## 3. Ative o GitHub Pages

Depois do primeiro envio, abra:

`Settings → Pages`

Em **Build and deployment**, escolha **GitHub Actions** como fonte.

O workflow `pages.yml` já faz o build e a publicação.

## 4. Espere o workflow terminar

Abra a aba **Actions** do repositório.

A execução chamada **Publicar simulador no GitHub Pages** deve passar pelas etapas de build e deploy.

Quando terminar, o GitHub exibirá a URL do site publicado no ambiente `github-pages`.

Ela terá um formato parecido com:

`https://SEU-USUARIO.github.io/simulador-radiacao-eletromagnetica/`

## 5. Coloque no Notion

Na sua folhinha, digite:

`/embed`

Cole a URL do GitHub Pages e confirme.

O simulador deverá aparecer dentro da página do Notion como conteúdo interativo.

## 6. Quando você alterar o simulador

Basta substituir o `main.py` no GitHub e fazer um novo commit. O GitHub Actions executará o build novamente e atualizará o site.
