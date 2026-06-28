# Tech stack — глубокий анализ для Avalone

> Это не просто список технологий, а архитектурное видение.
> Здесь разобраны trade-offs, эволюция по фазам и конкретные решения для каждого слоя.

## 1. Архитектурный подход: модульный монолит + извлекаемые сервисы

### Почему не микросервисы сразу

Микросервисы увеличивают сложность в 3-5 раз:
- distributed debugging;
- сетевые задержки (10-50 мс на вызов);
- необходимость SRE / platform engineers;
- сложное end-to-end тестирование;
- высокие инфраструктурные затраты ($4,200-8,500/мес против $1,100-2,300 для монолита).

По данным CNCF 2025, ~42% компаний, начавших с микросервисов, частично возвращаются к более крупным deployable units. Martin Fowler настаивает: "Monolith First".

### Почему не чистый монолит

Чистый монолит без границ превращается в спагетти. Нам нужны чёткие модули с самого начала.

### Рекомендуемый подход: Modular Monolith

- Один deployable unit.
- Внутри — чёткие bounded contexts: identity, reputation, graph, commute, payments, notifications.
- Модули общаются через in-process event bus.
- Каждый модуль имеет чёткие порты и адаптеры (hexagonal architecture).
- Когда какой-то модуль требует независимого масштабирования — извлекаем его в сервис.

### Что извлекаем первым при росте

1. **Real-time service** — WebSocket-соединения требуют особого масштабирования.
2. **Graph/recommendation service** — графовые вычисления могут есть много памяти.
3. **Notification service** — отправка push/SMS через очереди.

### Serverless для edge-сценариев

Managed functions для:
- обработки событий;
- фоновых рассылок;
- парсинга внешних данных;
- редких админских операций.

Это даёт гибкость без основной сложности микросервисов.

---

## 2. Frontend

### Почему PWA, а не нативное приложение

- Не нужно проходить App Store / Play Store review.
- Мгновенные обновления.
- Один codebase для iOS, Android, desktop.
- Можно установить на home screen.
- Дешевле в разработке и поддержке.

### Почему SvelteKit

| Критерий | SvelteKit | Next.js | Vue/Nuxt |
|----------|-----------|---------|----------|
| Размер bundle | Меньше | Больше | Средний |
| Производительность | Очень высокая | Высокая | Высокая |
| Learning curve | Средний | Низкий | Низкий |
| Экосистема | Растёт | Огромная | Большая |
| SSR/SSG | Да | Да | Да |
| PWA | Да | Да | Да |
| Код для AI/мобильных | Меньше boilerplate | Больше абстракций | Средне |

Svelte компилирует компоненты в оптимизированный vanilla JS, убирая виртуальный DOM. Это критично для мобильных устройств и медленного интернета.

### Альтернатива: Flutter

Если в будущем понадобится нативный опыт (например, deep integration с KakaoTalk, фоновая геолокация):
- Flutter — один codebase для 6 платформ.
- Собственный рендеринг — pixel-perfect UI.
- Стоимость MVP ~$70k-170k (дороже PWA, но дешевле двух нативных приложений).

**Рекомендация:** начать с PWA на SvelteKit. Flutter рассматривать только если PWA не закрывает критичные UX-сценарии.

### State management

- **Svelte stores** — для локального состояния.
- **TanStack Query** — для серверного состояния, кэширования, синхронизации.
- **Zustand или Pinia** — если растёт глобальное состояние.

### UI-библиотеки

- **Tailwind CSS** — utility-first, быстрая кастомизация.
- **shadcn-svelte** или **Skeleton UI** — готовые accessible компоненты.
- **Lucide icons** — современные иконки.

---

## 3. Backend

### Почему Python FastAPI

- Уже используется в Avalone — оператор и команда знакомы.
- Async из коробки (ASGI + uvicorn).
- Автоматическая OpenAPI документация.
- Отличная интеграция с ML/AI (PyTorch, scikit-learn, pandas).
- Типизация через Pydantic.

### Почему не Node.js / NestJS

- Node.js лучше для real-time, но у оператора уже Python-стек.
- Для ML/AI всё равно понадобится Python.
- Real-time можно вынести в отдельный сервис при необходимости.

### Структура backend

```
avalone/
├── api/              # REST + WebSocket endpoints
├── core/             # доменные модули
│   ├── identity/
│   ├── reputation/
│   ├── graph/
│   ├── commute/
│   ├── payments/
│   └── notifications/
├── infrastructure/   # адаптеры: БД, кэш, очереди, внешние API
├── workers/          # фоновые задачи
└── ml/               # модели matching / рекомендаций
```

### API design

- **REST** для CRUD и синхронных операций.
- **WebSocket** для real-time статусов.
- **gRPC** только при переходе к микросервисам.
- **GraphQL** — рассмотреть позже, если клиентам нужна гибкость запросов.

---

## 4. Data layer

### PostgreSQL как основа

**Зачем:**
- ACID, надёжность, сложные запросы.
- JSONB для гибких полу-структурированных данных.
- Full-text search.
- PostGIS для гео-данных.
- Знакомо по Avalone.

**Как моделировать граф в PostgreSQL:**

```sql
-- Узлы
CREATE TABLE entities (
    id UUID PRIMARY KEY,
    type TEXT NOT NULL, -- person, organization, place, event, opportunity
    data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Рёбра
CREATE TABLE relationships (
    id UUID PRIMARY KEY,
    from_entity UUID REFERENCES entities(id),
    to_entity UUID REFERENCES entities(id),
    type TEXT NOT NULL, -- works_for, drove_with, trusts, knows
    weight FLOAT DEFAULT 1.0,
    data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы для обхода графа
CREATE INDEX idx_rel_from ON relationships(from_entity, type);
CREATE INDEX idx_rel_to ON relationships(to_entity, type);
```

Для запросов типа "друзья друзей" использовать recursive CTE.

### Когда добавлять Neo4j

- Когда графовые запросы занимают >100 мс в PostgreSQL.
- Когда нужен обход 4+ уровней в глубину.
- Когда начинаем строить recommendation engine.
- Ориентировочно: при 10k+ пользователей или 100k+ связей.

### Кэширование

- **Redis** для:
  - сессий;
  - rate limiting;
  - кэша частых запросов;
  - pub/sub для real-time;
  - очередей задач.

### Event sourcing / CQRS (на будущее)

- События: "TripCreated", "PassengerPickedUp", "ShiftEnded".
- Event log в PostgreSQL.
- Read models обновляются асинхронно.
- Это даст аудит, восстановление состояния и аналитику.

---

## 5. Real-time architecture

### Почему WebSockets + Redis Pub/Sub

- WebSockets — persistent bidirectional connection.
- Redis Pub/Sub позволяет масштабировать на несколько серверов без sticky sessions.
- Сообщения между серверами доставляются <10 мс.

### Архитектура

```
Client ←→ Load Balancer ←→ WebSocket Server 1
                                  ↑
                                  ↓
                           Redis Pub/Sub
                                  ↑
                                  ↓
                           WebSocket Server 2
```

### Паттерны

- **Rooms / namespaces:** комната для каждой поездки, смены, организации.
- **Stateless WebSocket servers:** состояние в Redis, любой сервер может обработать reconnect.
- **SSE как fallback:** для односторонних уведомлений (push) — проще и надёжнее.

### Что не делать

- Не хранить состояние в памяти одного WebSocket-сервера.
- Не использовать long polling в production.

---

## 6. AI / ML layer

### Зачем AI в Avalone

- Matching водителей и пассажиров.
- Предсказание времени прибытия.
- Рекомендации вакансий / возможностей.
- Обнаружение мошенничества / фейковых профилей.
- Перевод сообщений между языками.

### Стек

- **Python** — основной язык ML.
- **scikit-learn / LightGBM** — для табличных моделей (matching, рекомендации).
- **Sentence Transformers** — для semantic search.
- **LangChain / LlamaIndex** — для LLM-агентов и обработки документов.
- **PostgreSQL + pgvector** — для векторного поиска.

### Модели matching

На старте — rule-based + простые ML-модели:
- география;
- вместимость;
- предпочтения;
- история поездок;
- репутация.

Потом — графовые embeddings (аналог TwHIN от Twitter).

---

## 7. Maps и гео

### Kakao Maps API

- Лучшее покрытие Кореи.
- Точные адреса и маршруты.
- Интеграция с KakaoTalk / KakaoPay.

### Что строим

- Точки сбора пассажиров.
- Маршруты машин.
- Геозоны заводов.
- ETA (estimated time of arrival).

### Fallback

- OpenStreetMap + Leaflet для разработки и тестирования.
- Naver Maps API как альтернатива Kakao.

---

## 8. Identity и Auth

### Фаза 1: Phone + Firebase Auth

- Быстрый старт.
- SMS verification.
- Social login (Kakao, Google).

### Фаза 2: Verifiable Credentials

- Самущили и заводы выдают credentials: "работал на заводе X", "имеет права".
- W3C VC Data Model.
- Хранение в пользовательском wallet.

### Фаза 3: DID

- Decentralized identifiers.
- Self-sovereign identity.
- Только когда экосистема созреет.

### Безопасность

- JWT с коротким TTL + refresh tokens.
- Rate limiting на auth endpoints.
- OAuth 2.1 / PKCE для мобильных/PWA.

---

## 9. Payments

### Фаза 1: Stripe

- Международный.
- Простой API.
- Подходит для тестирования моделей монетизации.

### Фаза 2: KakaoPay / Toss Payments

- Для корейского рынка.
- Требует корейской юрлица.
- Интеграция с KakaoTalk.

### Модели монетизации

- Комиссия с поездки.
- Подписка самонимов / организаций.
- Premium features для водителей.
- Реклама внутри платформы.

---

## 10. Интеграции

### KakaoTalk

- **Kakao Channel** для организаций.
- **Push notifications** через Kakao.
- **Share API** для приглашений.

### Kakao Map

- Геокодинг, маршруты, поиск мест.

### KakaoPay

- Расчёты между участниками (на фазе 2).

### SMS / Email

- Firebase / Twilio для SMS.
- SendGrid / AWS SES для email.

---

## 11. Security

### Уровни защиты

1. **Transport:** TLS 1.3 everywhere.
2. **Auth:** MFA для админов, phone verification для пользователей.
3. **API:** rate limiting, input validation, OWASP Top 10.
4. **Data:** encryption at rest, field-level encryption для PII.
5. **Infrastructure:** WAF (Cloudflare), DDoS protection.
6. **Secrets:** HashiCorp Vault или AWS Secrets Manager, никаких секретов в коде.

### Privacy by design

- Минимизация собираемых данных.
- Явное согласие пользователей.
- GDPR / PIPA (Korea) compliance roadmap.
- Data retention policies.

---

## 12. DevOps и observability

### Инфраструктура

- **Фаза 0:** MacBook + Cloudflare tunnel (как Avalone).
- **Фаза 1:** VPS (Hetzner / DigitalOcean / AWS Lightsail) + Docker.
- **Фаза 2:** Kubernetes или managed container platform.

### CI/CD

- GitHub Actions.
- Автоматические тесты.
- Staging environment.
- Blue-green или rolling deployment.

### Monitoring

- **Prometheus + Grafana** — метрики.
- **Loki** — логи.
- **Sentry** — ошибки.
- **Uptime monitoring** — Pingdom / UptimeRobot.

### Backup

- Автоматические бэкапы PostgreSQL.
- Point-in-time recovery.
- Тестирование восстановления.

---

## 13. Эволюция стека по фазам

### Фаза 0: Proof of Concept (1-2 месяца)

- SvelteKit PWA.
- FastAPI.
- PostgreSQL.
- WebSockets.
- Firebase Auth.
- Kakao Map.
- MacBook + Cloudflare tunnel.

**Цель:** показать, что развозку можно координировать через приложение.

### Фаза 1: MVP для одного самонима (2-4 месяца)

- Добавляем Redis (кэш + pub/sub).
- Basic reputation / ratings.
- Notifications (push + SMS).
- Stripe для платежей.
- VPS + Docker.

**Цель:** одна группа людей ездит через Avalone ежедневно.

### Фаза 2: Масштабирование (6-12 месяцев)

- Neo4j для графа.
- ML-модели matching.
- KakaoPay интеграция.
- Real-time service выделяем отдельно.
- Kubernetes.

**Цель:** несколько самущилей, сотни пользователей.

### Фаза 3: Метавселенная (1-2 года)

- DID/VC identity.
- Множество веток (работа, образование, туризм...).
- Graph-based recommendation engine.
- Third-party developers / mini-programs.

---

## 14. Итоговый рекомендуемый стек

| Слой | Технология | Альтернатива |
|------|-----------|--------------|
| Frontend | SvelteKit PWA | Next.js / Flutter |
| Backend | Python FastAPI | Node.js / NestJS |
| Architecture | Modular monolith | Microservices (позже) |
| Database | PostgreSQL | MySQL |
| Graph (позже) | Neo4j | Dgraph / Apache AGE |
| Cache / Pub-Sub | Redis | Memcached / RabbitMQ |
| Real-time | WebSockets + Redis Pub/Sub | SSE / Ably |
| Auth | Firebase Auth | Auth0 / Clerk |
| Maps | Kakao Maps API | Naver Maps |
| Payments | Stripe → KakaoPay | Toss Payments |
| ML | Python + scikit-learn + pgvector | Spark / TensorFlow |
| Hosting | VPS + Docker → Kubernetes | AWS ECS / Google Cloud Run |
| Monitoring | Prometheus + Grafana + Sentry | Datadog / New Relic |
| CI/CD | GitHub Actions | GitLab CI |

---

## Sources

- Modern Software Architecture 2026: https://www.softwareseni.com/understanding-modern-software-architecture-from-microservices-consolidation-to-modular-monoliths/
- Microservices vs Monoliths 2026: https://www.javacodegeeks.com/2025/12/microservices-vs-monoliths-in-2026-when-each-architecture-wins.html
- Monolith vs Microservices Decision Framework: https://www.agilesoftlabs.com/blog/2026/02/monolith-vs-microservices-decision
- Graph DB vs Relational DB: https://neo4j.com/blog/graph-database/graph-database-vs-relational-database/
- Postgres vs Neo4j: https://pgbench.com/comparisons/postgres-vs-neo4j
- Real-Time Web App Guide 2026: https://www.gitnexa.com/blogs/real-time-web-app-development-guide
- Scaling Pub/Sub with WebSockets and Redis: https://ably.com/blog/scaling-pub-sub-with-websockets-and-redis
- Flutter vs React Native 2026: https://catdoes.com/blog/flutter-vs-react-native-2026
- PWA vs Cross-Platform 2026: https://wearepresta.com/mobile-app-strategy-native-crossplatform-or-progressive-web-app/
