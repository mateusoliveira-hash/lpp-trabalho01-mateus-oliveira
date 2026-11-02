# Estaleiro em Tempo Real — 17 - Estaleiro (madeira → barcos)

Vila em tempo real orientada a eventos: o Mestre abre a temporada e aceita encomendas, os Jogadores constroem docas e entregam barcos. O servidor guarda o estado, decide cada pedido e anuncia os fatos para todos. As regras e o catálogo de eventos estão em [`docs/especificacao.md`](docs/especificacao.md).

## Integrantes
- Mateus Vinicios de Oliveira - @mateusoliveira-hash

## Como instalar e executar
Requisitos: Python 3 e um navegador com acesso à internet (Vue, Socket.IO e Phaser são carregados por CDN).

```bash
git clone https://github.com/mateusoliveira-hash/lpp-trabalho01-mateus-oliveira.git
cd lpp-trabalho01-mateus-oliveira
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn server:app --reload
```

Abra **http://localhost:8000** no navegador (pelo endereço, não pelo arquivo). Se a porta 8000 estiver ocupada, use `uvicorn server:app --reload --port 8001` e abra http://localhost:8001.

## Como testar com duas abas
1. Abra duas abas em http://localhost:8000.
2. **Aba 1:** digite um nome e clique em **Entrar como Mestre**. **Aba 2:** digite outro nome e clique em **Entrar como Jogador**. As duas recebem `estado.sincronizado` com 150 de madeira e 0 barcos.
3. **Recusa por fase:** na aba do Jogador, clique em **Construir Doca** antes de abrir. Só ela recebe `operacao.recusada` com "A temporada não está aberta"; a aba do Mestre não muda.
4. **Abertura:** no Mestre, clique em **Abrir temporada**. As duas abas recebem `vila.iniciada`, e a cada 5 s chega `recurso.produzido` com +15 de madeira, sem ninguém clicar.
5. **Construção:** no Jogador, clique em **Construir Doca**. As duas abas recebem `construcao.iniciada` (madeira −50, carpinteiros 1/3). Após 10 s chega `construcao.concluida` e a doca aparece pronta.
6. **Barcos:** com a doca pronta, cada `recurso.produzido` passa a trocar 10 de madeira por 1 barco (+5 de madeira e +1 barco por ciclo).
7. **Recusa por madeira:** clique em **Construir Doca** várias vezes seguidas até faltar madeira ou carpinteiro: aparece "Madeira insuficiente" ou "Sem carpinteiro livre".
8. **Encomenda expirada:** no Mestre, clique em **Aceitar encomenda** (`encomenda.recebida` nas duas abas). Clicar de novo gera "Já existe uma encomenda em andamento". Sem entregar, após 45 s chega `encomenda.expirada` e o contador de expiradas sobe, sem mexer nos barcos.
9. **Encomenda entregue:** com pelo menos 3 barcos, o Mestre aceita uma nova encomenda e o Jogador clica em **Entregar encomenda**: as duas abas recebem `encomenda.entregue` (barcos −3, madeira +100, entregas +1). Com menos de 3 barcos, a recusa é "Barcos insuficientes".
10. **Disputa:** com uma terceira aba como Jogador, os dois Jogadores clicam em **Entregar encomenda** ao mesmo tempo: um recebe `encomenda.entregue` e o outro "Não há encomenda para entregar".
11. **Encerramento:** no Mestre, clique em **Encerrar temporada**. Todas as abas recebem `vila.encerrada`; a produção para, obras e encomendas pendentes não terminam e novos pedidos são recusados.

Em todos os passos, o **Painel de eventos** mostra cada `⬆ emit` e `⬇ on`, com a causa e a reação, e os contadores por evento no topo.

## Perguntas
1. **Quais eventos o seu sistema emite e escuta?**
   - **Pedidos** (o cliente emite, o servidor escuta): `vila.abertura_solicitada`, `construcao.solicitada`, `encomenda.criacao_solicitada`, `encomenda.entrega_solicitada` e `vila.encerramento_solicitado`.
   - **Fatos** (o servidor emite, os clientes escutam): `estado.sincronizado` e `operacao.recusada` (só para uma aba); `vila.iniciada`, `construcao.iniciada`, `recurso.produzido`, `construcao.concluida`, `encomenda.recebida`, `encomenda.entregue`, `encomenda.expirada` e `vila.encerrada` (para todos).
   - Três fatos não nascem de clique, e sim de temporizadores do servidor: `recurso.produzido`, `construcao.concluida` e `encomenda.expirada`.

2. **Como o sistema sabe quando deve atualizar os outros jogadores?**
   O cliente nunca pergunta se algo mudou. Sempre que o servidor altera o estado, ele emite um fato **sem `to=`**, que vai para todos os conectados, e cada cliente atualiza a tela ao receber (push, não polling). Quando nada muda para os outros, o servidor usa `to=sid` e só a aba envolvida recebe: é o caso de `operacao.recusada` e de `estado.sincronizado`.

3. **Que parte do código mostra claramente o uso do paradigma orientado a eventos?**
   O par `@sio.on("encomenda.entrega_solicitada")` no `server.py` e `ouvir("encomenda.entregue", ...)` no `index.html`. Nenhuma das duas funções é chamada diretamente pelo nosso código: elas ficam registradas, e o laço de eventos as chama quando o evento chega (inversão de controle). O servidor valida, altera o estado e avisa todos sem nenhum `await` no meio, então numa disputa só o primeiro pedido encontra a encomenda. Também a função `prazo_encomenda`, em que a própria passagem do tempo vira um evento (`encomenda.expirada`) sem clique de ninguém.

## Uso de IA
Usei o **Claude Code** (Anthropic) como mentor durante todo o trabalho. Ele explicou os conceitos de programação orientada a eventos, revisou a especificação, revisou trechos de código que eu digitei e commitei etapa por etapa, conferiu cada etapa com testes automáticos (clientes simulados) e apontou erros como nomes de eventos digitados errado. 

## Extras
- **Contadores por evento** no Painel de eventos (Etapa 7, obrigatória só para duplas): mostram quantas vezes cada evento foi enviado ou recebido por aquela aba.
