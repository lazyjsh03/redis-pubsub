## Django와 Redis를 활용한 Pub/Sub 및 메시지 큐 시스템 해설

이 문서는 현재 Django 프로젝트에 구현된 Redis의 Pub/Sub 및 메시지 큐 기능의 작동 방식을 설명합니다. 전체적인 데이터 흐름과 각 구성 요소의 역할을 이해하기 쉽게 정리했습니다.

### 1. Redis란 무엇이며 왜 사용할까요?

Redis는 "REmote DIctionary Server"의 약자로, 메모리 기반의 키-값(Key-Value) 구조 데이터 저장소입니다. 빠른 속도를 장점으로 하며, 단순한 데이터베이스를 넘어 다양한 자료구조를 지원하여 캐시, 세션 관리 등 여러 목적으로 사용됩니다.

이 프로젝트에서는 Redis의 핵심 기능 중 하나인 **Pub/Sub** 모델을 활용하여 **메시지 브로커(Message Broker)** 역할을 수행하도록 구현했습니다.

*   **메시지 브로커:** 메시지를 보내는 애플리케이션(Publisher)과 메시지를 받는 애플리케이션(Subscriber) 사이에서 메시지를 안정적으로 중개하고 전달하는 시스템입니다.

### 2. 핵심 개념: Pub/Sub (Publish/Subscribe)

Pub/Sub은 특정 채널(Channel)을 중심으로 메시지를 주고받는 통신 모델입니다.

*   **Publisher (발행자):** 특정 채널에 메시지를 **발행(Publish)**하는 주체입니다. 메시지를 보낼 뿐, 누가 이 메시지를 받을지에 대해서는 알지 못합니다.
*   **Subscriber (구독자):** 특정 채널을 **구독(Subscribe)**하고 있다가, 해당 채널에 새로운 메시지가 발행되면 이를 수신하여 처리하는 주체입니다.
*   **Channel (채널):** 발행자와 구독자 사이의 연결 고리 역할을 하는 논리적인 통로입니다. 구독자는 관심 있는 채널만 구독하며, 발행자는 특정 채널을 지정하여 메시지를 보냅니다.



이 모델을 사용하면 각 서비스(발행-구독) 간의 **결합도(Coupling)**가 낮아집니다. 즉, 서로의 존재를 직접 알지 못해도 Redis라는 중간 다리를 통해 소통할 수 있어 시스템을 더 유연하고 확장 가능하게 만듭니다.

### 3. 프로젝트 아키텍처 및 데이터 흐름

이 프로젝트에서 사용자가 새로운 Todo 항목을 생성하거나 상태를 변경할 때, Redis Pub/Sub을 통해 어떤 일이 일어나는지 순서대로 살펴보겠습니다.

#### 흐름 요약

1.  **[Django View]** 클라이언트(사용자)가 API를 통해 Todo 관련 요청(생성/수정)을 보냅니다.
2.  **[Django View]** 요청을 받은 View는 데이터베이스에 변경 사항을 저장합니다.
3.  **[Publisher]** 데이터 변경이 완료된 후, View 또는 관련 로직(예: `pubsub.py`)에서 Redis의 특정 채널(예: `todo_updates`)로 변경에 대한 메시지를 **발행(Publish)**합니다.
4.  **[Redis]** Redis 서버는 이 메시지를 수신하고, `todo_updates` 채널을 구독하고 있는 모든 구독자에게 메시지를 즉시 전달합니다.
5.  **[Subscriber]** 백그라운드에서 실행 중인 구독자(`pubsub.py`의 `listen_for_messages` 함수)는 메시지를 수신합니다.
6.  **[Subscriber]** 수신된 메시지(예: "Todo가 생성되었습니다")를 바탕으로 특정 작업(예: 로그 기록, 캐시 업데이트, 다른 시스템에 알림 전송 등)을 수행합니다.

#### 시각적 흐름도

```
+-----------+      +----------------+      +-------------+      +------------------+
|           |      |                |      |             |      |                  |
|   User    |----->|  Django Views  |----->|  Publisher  |----->|   Redis Server   |
|           |      | (API Endpoint) |      |             |      | (Message Broker) |
+-----------+      +----------------+      +-------------+      +------------------+
                         |                                               |
                         | (DB Save)                                     | (Message Delivered)
                         v                                               v
                  +------------+                            +----------------------+
                  |            |                            |                      |
                  | PostgreSQL |                            |  Subscriber Process  |
                  |  Database  |                            | (Background Worker)  |
                  +------------+                            +----------------------+
                                                                       |
                                                                       | (Process Message)
                                                                       v
                                                                 +-------------+
                                                                 |             |
                                                                 |   Action    |
                                                                 | (e.g., Log) |
                                                                 +-------------+
```

### 4. 코드 레벨 분석

프로젝트의 주요 파일들이 이 흐름에서 어떤 역할을 하는지 살펴보겠습니다.

*   **`djrtodoprj/todo/views.py` (또는 관련 로직)**
    *   클라이언트의 요청을 직접 처리하는 부분입니다.
    *   Todo 모델 객체를 생성하거나 수정한 후, `pubsub.py`에 정의된 발행 함수를 호출하여 Redis에 메시지를 보냅니다.

    ```python
    # 예시: views.py 내의 코드 조각
    from . import pubsub

    def create_todo(request):
        # ... 데이터베이스에 Todo 저장 로직 ...
        new_todo.save()

        # Redis 채널로 메시지 발행
        message = f"새로운 Todo 생성: {new_todo.title}"
        pubsub.publish_message('todo_updates', message)

        return Response(...)
    ```

*   **`djrtodoprj/todo/pubsub.py`**
    *   Redis와의 통신을 직접 담당하는 핵심 파일입니다.
    *   **`publish_message` 함수:** 메시지를 발행하는 역할을 합니다. Django의 어느 곳에서든 이 함수를 호출하여 특정 채널에 메시지를 보낼 수 있습니다.
    *   **`listen_for_messages` (또는 유사한 이름의) 함수:** 특정 채널을 구독하고 메시지를 실시간으로 수신 대기하는 역할을 합니다. 이 스크립트는 Django 서버와는 별개의 프로세스로 백그라운드에서 계속 실행되어야 합니다.

    ```python
    # pubsub.py
    import redis

    # Redis 서버 연결
    r = redis.Redis(host='localhost', port=6379, db=0)

    def publish_message(channel, message):
        """지정된 채널로 메시지를 발행합니다."""
        print(f"'{channel}' 채널로 메시지 발행: {message}")
        r.publish(channel, message)

    def listen_for_messages():
        """백그라운드에서 실행되며 채널을 구독하고 메시지를 처리합니다."""
        p = r.pubsub()
        p.subscribe('todo_updates')
        print("'todo_updates' 채널 구독 시작...")

        for message in p.listen():
            if message['type'] == 'message':
                # 메시지 수신 시 수행할 작업
                data = message['data'].decode('utf-8')
                print(f"메시지 수신: {data}")
                # 예: 로그 파일에 기록, 캐시 데이터 갱신 등
    ```

*   **`docker/docker-compose.yml`**
    *   프로젝트에 필요한 서비스(Django 앱, PostgreSQL 데이터베이스, Redis 서버)를 정의하고 함께 실행할 수 있도록 설정하는 파일입니다.
    *   이 파일을 통해 Redis 컨테이너가 실행되고, Django 애플리케이션이 `redis:6379`와 같은 주소로 Redis 서버에 접근할 수 있게 됩니다.

### 5. 실행 및 관리

*   **구독자(Subscriber) 실행:** `pubsub.py`의 `listen_for_messages` 함수는 항상 실행 상태를 유지해야 메시지를 놓치지 않습니다. 보통 `python manage.py`와 같은 명령어로 사용자 정의 커맨드를 만들어 실행하거나, 별도의 터미널에서 직접 `python djrtodoprj/todo/pubsub.py`를 실행하여 백그라운드 워커(Worker)로 둡니다.

*   **Celery와 함께 사용하기:** 더 정교한 시스템에서는 Celery와 같은 분산 작업 큐(Distributed Task Queue) 프레임워크를 함께 사용합니다. 이 경우 Redis는 Celery의 메시지 브로커 역할을 하게 되며, 구독 로직은 Celery '작업(Task)'으로 정의되어 더 안정적이고 체계적으로 관리될 수 있습니다. (현재 프로젝트의 `tasks.py` 파일은 이러한 확장을 염두에 둔 구조일 수 있습니다.)

### 결론

이 프로젝트는 Redis의 Pub/Sub 기능을 활용하여 Django 애플리케이션의 특정 이벤트(Todo 변경)를 비동기적으로 처리하는 방법을 보여줍니다. 이를 통해 이벤트 발생 부분과 처리 부분을 분리하여 시스템의 유연성을 높이고, 실시간 알림이나 데이터 동기화 등 다양한 기능으로 확장할 수 있는 기반을 마련했습니다.
