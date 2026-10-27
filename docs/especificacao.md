# Especificação Vila em Tempo Real: Estaleiro

**Integrante:** Mateus Vinicios de Oliveira — @mateusoliveira-hash
**Tipo de vila (sorteio):** 17 - Estaleiro (madeira → barcos)

## 1. Regras da vila

### Papéis
- **Mestre** (dono do estaleiro): abre e encerra a temporada e aceita encomendas de barcos.
- **Jogador** (encarregado dos carpinteiros): constrói docas e entrega encomendas.
- Todos veem o mesmo estaleiro. Só o Servidor altera o estado; os participantes apenas pedem e mostram o que o Servidor anuncia.

### Recursos e números
- Recurso primário: **madeira**. Começa com **150**.
- Recurso refinado: **barcos**. Começa com **0**.
- Construção: **doca**. Custa **50 de madeira** e fica pronta em **10 segundos**.
- Trabalhadores: **carpinteiros**, limite de **3**. Cada doca em obra ocupa 1 carpinteiro até ficar pronta.
- Produção automática: a cada **5 segundos**, o estaleiro recebe **+15 de madeira**.
- Refino: a cada ciclo de produção, **cada doca concluída transforma 10 de madeira em 1 barco**, enquanto houver madeira suficiente.
- Quando uma obra termina: o carpinteiro fica livre e o estaleiro passa a ter uma doca a mais (mais barcos por ciclo).

### Encomendas (evento próprio: o que expira)
- O Mestre aceita uma encomenda de **3 barcos** com prazo de **45 segundos**. Só existe **uma encomenda por vez**.
- Um Jogador entrega a encomenda: o estaleiro perde **3 barcos** e recebe **100 de madeira** como pagamento.
- Se o prazo acabar antes da entrega, a encomenda **expira** e não há pagamento.

### Temporada
- Fases: **aguardando → aberta → encerrada**.
- Só o Mestre abre e encerra a temporada.
- Com a temporada encerrada, a produção para, obras em andamento não terminam, encomendas pendentes são descartadas e qualquer novo pedido é recusado.

### Motivos de recusa
| Pedido | Recusado quando | Motivo informado |
|---|---|---|
| abrir temporada | quem pediu não é o Mestre / temporada já foi aberta | "Só o Mestre pode abrir a temporada" / "A temporada já foi aberta" |
| construir doca | temporada não está aberta / madeira < 50 / 3 carpinteiros ocupados | "A temporada não está aberta" / "Madeira insuficiente" / "Sem carpinteiro livre" |
| encerrar temporada | quem pediu não é o Mestre / temporada não está aberta | "Só o Mestre pode encerrar a temporada" / "A temporada não está aberta" |
| aceitar encomenda | quem pediu não é o Mestre / temporada não está aberta / já existe encomenda | "Só o Mestre pode aceitar encomendas" / "A temporada não está aberta" / "Já existe uma encomenda em andamento" |
| entregar encomenda | temporada não está aberta / não há encomenda / barcos < 3 | "A temporada não está aberta" / "Não há encomenda para entregar" / "Barcos insuficientes" |

## 2. Eventos

Padrão de nomes: `objeto.acao_solicitada` para pedidos de um participante; `objeto.acao_no_passado` para fatos confirmados pelo Servidor.

| Evento | Tipo | Emite | Recebe | Causa | O que muda no estado |
|---|---|---|---|---|---|
| `estado.sincronizado` | fato | Servidor | Só quem entrou | entrada no estaleiro | Nada muda; o recém-chegado recebe o estado completo |
| `vila.abertura_solicitada` | pedido | Mestre | Servidor | clique | Nada (é um pedido) |
| `vila.iniciada` | fato | Servidor | Todos | `vila.abertura_solicitada` | Fase passa a **aberta**; a produção automática começa |
| `construcao.solicitada` | pedido | Jogador | Servidor | clique | Nada (é um pedido) |
| `construcao.iniciada` | fato | Servidor | Todos | `construcao.solicitada` | Madeira −50; carpinteiros ocupados +1; docas em obra +1 |
| `operacao.recusada` | fato | Servidor | Só quem pediu | qualquer pedido inválido | Nada muda; informa o motivo |
| `recurso.produzido` | fato | Servidor | Todos | temporizador (a cada 5 s) | Madeira +15; cada doca concluída troca 10 de madeira por 1 barco |
| `construcao.concluida` | fato | Servidor | Todos | `construcao.iniciada` + temporizador (10 s) | Carpinteiros ocupados −1; docas em obra −1; docas concluídas +1 |
| `encomenda.criacao_solicitada` | pedido | Mestre | Servidor | clique | Nada (é um pedido) |
| `encomenda.recebida` | fato | Servidor | Todos | `encomenda.criacao_solicitada` | Passa a existir uma encomenda de 3 barcos com prazo de 45 s |
| `encomenda.entrega_solicitada` | pedido | Jogador | Servidor | clique | Nada (é um pedido) |
| `encomenda.entregue` | fato | Servidor | Todos | `encomenda.entrega_solicitada` | Barcos −3; madeira +100; encomenda deixa de existir; entregas +1 |
| `encomenda.expirada` | fato | Servidor | Todos | `encomenda.recebida` + temporizador (45 s) | Encomenda deixa de existir sem pagamento; expiradas +1 |
| `vila.encerramento_solicitado` | pedido | Mestre | Servidor | clique | Nada (é um pedido) |
| `vila.encerrada` | fato | Servidor | Todos | `vila.encerramento_solicitado` | Fase passa a **encerrada**; produção, obras e encomendas param |

## 3. Cenários de teste (Dado / Quando / Então, escritos com eventos)

### Recusa
Dado que há menos de 50 de madeira disponível, a temporada está aberta e há um carpinteiro livre, quando o jogador emite `construcao.solicitada`, então o servidor emite `operacao.recusada` para o jogador que solicitou a construção manda só o motivo "Madeira insuficiente".

### Passagem do tempo
Dado que o Servidor emitiu `encomenda.recebida`, quando o tempo de 45 segundos foi atingido e `encomenda.entregue` não foi emitido, então o evento `encomenda.expirada` é enviado pelo temporizador a todos e a encomenda deixa de existir devido a expiração do prazo não alterando o número de barcos disponíveis.

### Disputa entre dois jogadores
Dado que a temporada está aberta, há somente 3 barcos disponíveis, o servidor emitiu `encomenda.recebida`, quando os jogadores A e B emitem `encomenda.entrega_solicitada` ao mesmo tempo, então o servidor atende a um pedido por vez: para o primeiro emite `encomenda.entregue` para todos os jogadores, com a encomenda deixando de existir, para o segundo emite `operacao.recusada` somente para o jogador com o motivo "Não há encomenda para entregar", e o estado não muda.