# Cover RF Sync

**Cover lógica** que sincroniza o movimento de um portão/persiana com base em **tempo** e, opcionalmente, **sensores** de início de movimento, com suporte a **script** externo (ex.: pulso RF).

![Logo](assets/logo.png)

> Integration type: **helper**; IoT class: **calculated**.
> Documentação oficial sobre manifest e integration_type.  
> Documentação oficial sobre Options Flow (botão **Configurar** / reconfiguração).  

## Funcionalidades
- **Script configurável** por entidade; serviço `cover_rf_sync.activate_script`.
- **Arranque por sensor** (se existir): após chamar o script, o movimento **só** começa quando o sensor da direção pedida mudar para **on**.
- **Replicação** quando o **sensor** dispara (sem correr script).
- **Tempos separados** de abertura/fecho.
- **Tolerância (%)** configurável (aviso >25%).
- **Botões dinâmicos**: parado → só **Abrir** ou só **Fechar**; em movimento → **Abrir/Fechar/Parar**.

## Instalação

### Via HACS (recomendado)
1. Em **HACS → Integrações**, adiciona este repositório como **Repositório Personalizado**:  
   `https://github.com/FragMenthor/home-assistant-custom-components-cover-rf-sync`
2. Instala **Cover RF Sync** e **reinicia** o HA.

### Manual
1. Copia `custom_components/cover_rf_sync` para `config/custom_components/`.
2. Reinicia o HA.

## Adicionar e reconfigurar
- **Adicionar**: Definições → Dispositivos e Serviços → **Adicionar Integração** → *Cover RF Sync*.
- **Configurar**: escolhe **Script**, **Nome**, **Tempos** (abertura/fecho), **Tolerância (%)**, **Sensores** (opcionais).
- **Reconfigurar**: carta da integração → **Configurar** (Options Flow).

## Serviço
```yaml
service: cover_rf_sync.activate_script
data:
  entity_id: cover.portao
```
- Chama o `script` da entidade. Se existir sensor para a direção esperada, aguarda o **sensor** antes de iniciar a simulação.

## Lógica da próxima ação
- **Fechado →** Abrir  
- **A abrir →** Parar  
- **Aberto →** Fechar  
- **A fechar →** Parar  
- **Parou a meio (10–90%) →** próxima ação **inversa** (tolerância configurável).

## Limitações do frontend
- O tile nativo não suporta **STOP‑only**; em movimento mostra **Abrir/Fechar/Parar** (comportamento padrão do HA).

## Compatibilidade e metadados
- `integration_type: "helper"` (evita default “hub”).
- `iot_class: "calculated"` (entidades derivadas).

## Changelog
**0.9.0**  
- Domínio **`cover_rf_sync`** e nome **Cover RF Sync**.  
- Options Flow com aviso de tolerância alta.  
- Arranque condicionado por sensor após chamada de script.  
- Tempos separados e botões dinâmicos.

## Licença
MIT
