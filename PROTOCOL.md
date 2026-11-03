# Protocolo BLE da Galp Pluma (deduzido)

Baseado em: uma captura HCI da app Mundo Galp e leituras com um script em
**três garrafas** (butano e propano; duas pareadas com a app, uma nunca pareada).
Tudo o que está marcado como **hipótese** não está confirmado.

## Dispositivo

- Anuncia-se como `Pluma--<11 dígitos>` (Silicon Labs). A deteção da integração
  não distingue maiúsculas de minúsculas.
- **O número do nome não é o código impresso na garrafa.** Nas três garrafas, o
  número do nome Bluetooth, o código de 5 caracteres do QR e o identificador do
  link NFC são três valores diferentes. Testei conversões de base (decimal,
  hexadecimal, base 36), partes dos números e o MAC, e não encontrei nenhuma
  relação simples. **Hipótese:** a correspondência entre eles está no servidor da
  Galp.
- O link NFC leva um identificador de 8 bytes que começa por `E0 04 01`. O
  prefixo `E0` e o código de fabricante `04` (NXP) são os de um UID ISO 15693,
  o que sugere que é o UID da etiqueta NFC e não um identificador do módulo
  Bluetooth (dedução, não confirmada). O mesmo endereço da Galp aceita esse UID
  ou o código de 5 caracteres.
- Aceita ligação **sem emparelhamento**.
- Faz *deep sleep*: só aceita ligações em janelas curtas.
- Apenas um cliente de cada vez.

## GATT

Serviço personalizado `d973f2e0-b19e-11e2-9e96-0800200c9a66`:

| Característica | Propriedades | Uso |
|---|---|---|
| `d973f2e1-b19e-11e2-9e96-0800200c9a66` | write, notify | Comandos e respostas (handle de valor `0x0015`, CCCD `0x0016`) |
| `d973f2e3-b19e-11e2-9e96-0800200c9a66` | write, notify | Desconhecido. **Nunca escrever** (pode ser OTA ou configuração). |

Também expõe os serviços standard Generic Access, Generic Attribute e Device
Information (só fabricante `2a29` e system id `2a23`; não há número de modelo).

## Sequência usada pela app

1. Ativar notificações na `d973f2e1` (escrever `0100` no CCCD).
2. Escrever o comando `HELLO` (sem resposta).
3. Escrever o comando `STATUS`.
4. Receber uma notificação de 11 bytes.

A app repete os passos 2 a 4 uma segunda vez; o script e a integração fazem só
uma e funciona.

## Comandos (6 bytes)

```
cmd(1) | chave(4) = 6a e8 ec a5 | checksum(1)
```

- `checksum = (soma dos bytes anteriores + 0xAA) & 0xFF`
- `HELLO`  = `55 6a e8 ec a5 e2`
- `STATUS` = `03 6a e8 ec a5 90`

A chave funcionou nas três garrafas. **Hipótese:** é uma constante do produto.

## Resposta ao STATUS (11 bytes)

```
idx:  0  1  2  3  4  5  6  7  8  9  10
      03 01 00 00 00 00 00 b7 TT LV CS
```

| Byte | Significado |
|---|---|
| 0 | `03` (eco do comando) |
| 1 | `01` (constante nas amostras) |
| 2-6 | `00` (constantes nas amostras) |
| 7 | **Desconhecido.** Varia por garrafa (112-113, 130-131, 122) e ±1 entre leituras. Não é um código de modelo nem de gás: as duas garrafas de propano têm valores diferentes (131 e 122). |
| 8 | **Temperatura em °C**, com sinal. Igual à da app em 4 de 4 leituras (22, 16, 14, 18). |
| 9 | **Nível em %, aproximado.** Ver abaixo. |
| 10 | Checksum, mesmo algoritmo dos comandos |

O tipo de gás (butano ou propano) **não** está nesta frame: os bytes 1 a 6 são
iguais nas garrafas de butano e de propano.

### Nível (byte 9) contra a app

| Garrafa | Byte 9 | App | Diferença |
|---|---|---|---|
| A (butano) | 89 | 89 % | 0 |
| A | 88 | 88 % | 0 |
| A | 90 | 88 % | +2 |
| B (propano, nova) | 97 | 100 % | -3 |
| C (propano, vazia) | 0 | 0 % | 0 |

- O byte 9 acompanha o nível (a garrafa vazia dá 0 e a cheia dá 97), mas **nem
  sempre coincide com a app**.
- O sensor tem ruído: duas notificações com 0,7 s de intervalo, na mesma
  garrafa, deram 90 e 89.
- **Hipóteses para a diferença (nenhuma testada):** a app filtra ou faz a média
  de várias leituras; ou aplica uma calibração por modelo de garrafa vinda do
  servidor; ou arredonda perto do cheio.

## Amostras reais

| Garrafa | Frame | Nível | Temp. | Byte 7 |
|---|---|---|---|---|
| A | `0301000000000070175a8f` | 90 | 23 | 112 |
| A | `030100000000007017598e` | 89 | 23 | 112 |
| A | `030100000000007116588d` | 88 | 22 | 113 |
| A | `0301000000000071105a89` | 90 | 16 | 113 |
| B | `03010000000000821461a5` | 97 | 20 | 130 |
| B | `03010000000000830e61a0` | 97 | 14 | 131 |
| C | `030100000000007a12003a` | 0 | 18 | 122 |

## Por descobrir

- O que é o byte 7.
- Como a app obtém o nível exato (filtro, calibração, outro comando).
- Onde está o tipo de gás e o modelo da garrafa (outro comando, ou só no
  servidor).
- Se a chave é mesmo igual em todas as garrafas.
- O que faz a característica `d973f2e3`.
- Se há outros comandos (por exemplo, consumo acumulado ou histórico).
