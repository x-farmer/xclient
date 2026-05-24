# XClient Python Coding Style

本文件定義 xclient 撰寫與修改 Python 程式碼時的 coding style rule，
適用於所有開發人員與 AI agent。

本文以本專案實務為準，並整理自以下參考：

- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Google Python Vim indentation settings](https://google.github.io/styleguide/google_python_style.vim)

若本文件、工具設定與外部 style guide 有衝突，優先順序為：

1. 本文件。
2. Codebase 內既有 formatter、linter、type checker 與測試設定。
3. 鄰近檔案既有風格。
4. Google Python Style Guide。

## 核心原則

XClient Python 程式碼必須優先滿足以下目標，順序不可顛倒：

1. 清晰：讀者能理解 CLI 命令會做什麼、資料從哪裡來，以及錯誤如何回報。
2. 可維護：domain、use case、adapter、CLI wiring 的責任邊界明確。
3. 型別可讀：用 type annotations 表達穩定契約，避免讓 runtime 才暴露可由型別捕捉的錯誤。
4. 可測試：核心規則與 use case 不依賴 terminal、network、config file 或外部服務即可測試。
5. 一致：遵守本文件、工具設定與同 package 既有寫法。

若規則之間有衝突，優先選擇更清楚、更容易維護、較不容易誤用的寫法。

## 檔案、格式與 Imports

- 所有 Python 檔案使用 UTF-8，檔名使用 `lower_with_under.py`，不得使用 dash。
- 程式區塊縮排使用 4 spaces，不使用 tabs。
- 不使用 semicolon 結束行，也不把多個 statement 塞在同一行。
- 避免使用反斜線做 line continuation；優先使用括號、方括號或大括號的 implicit line joining。
- Top-level function 或 class 之間保留兩個空行；method 之間保留一個空行。
- 檔案順序固定為：module docstring、imports、module constants/type aliases、implementation。
- Imports 放在檔案頂部，依序分組：`__future__` imports、standard library、third-party、本專案 package。
- Imports 應各自成行；`typing` 與 `collections.abc` 可在同一行 import 多個 type symbol。
- 優先 import package 或 module，不直接 import 一般 function/class/type。例外是 typing、collections.abc、typing_extensions，或為了避免名稱衝突與過長路徑而清楚 alias。
- 新程式碼使用完整 package path，不依賴目前 working directory 或 script 所在目錄進入 `sys.path` 的副作用。
- Side-effect import 只能用於明確需要註冊 side effect 的情境，且必須以註解說明原因。

```python
from __future__ import annotations

from collections.abc import Mapping, Sequence
import logging

import httpx

from xclient.application import chat_completion
from xclient.domain import conversation
```

## 命名

- Package、module、function、method、parameter、local variable 使用 `lower_with_under`。
- Class、exception 與公開 type alias 使用 `CapWords`。
- Module-level constant 使用 `CAPS_WITH_UNDER`；internal constant 使用 `_CAPS_WITH_UNDER`。
- Internal module、function、method 或 attribute 使用單一 `_` prefix。避免用雙底線 name mangling，除非有非常明確的 Python 語意需求。
- Exception class 名稱以 `Error` 結尾，且不要重複 module 名稱，例如避免 `client.ClientError`。
- 名稱必須描述 domain 或 application 語意，不使用只有局部團隊才懂的縮寫。
- 名稱長度應與 scope 成正比。短 scope 可使用 `i`、`e`、`f` 等慣例名稱；跨多行或跨概念時必須使用更明確名稱。
- 不在名稱中重複型別已表達的資訊，例如避免 `name_list`、`id_to_name_dict` 這類無助於語意的型別後綴。
- CLI option、environment variable 與 config key 的名稱若跨越外部 contract，必須與文件化 contract 保持一致。

## Docstrings 與註解

本專案要求「必要註解必須撰寫」。註解不是裝飾，而是 API 契約、
CLI 行為與維護知識的一部分。

只重述 module、class、function 或變數名稱的 docstring 不合格。這類
docstring 即使能滿足形式要求，也視為缺少文件。例如
`"""Client class."""`、`"""Calls the API."""`、`"""Stores config."""`
都不是有效文件。

合格 docstring 必須補足讀者無法只從名稱、signature 與 type hints
安全推論出的資訊：責任邊界、呼叫者義務、錯誤語意、resource
lifecycle、CLI stdout/stderr/exit-code contract、credential/security
assumption、相容性限制，或為何採用某個取捨。

### 必須撰寫 Docstring 的情況

- 所有 public module、class、exception、function、method、protocol 與 constant 必須有 docstring。
- 非 trivial size、non-obvious logic、或跨 layer boundary 的 internal function/method 也必須有 docstring。
- Use case、port/protocol、CLI command adapter、HTTP/API adapter、config loader、credential/token handler、stream handler、retry helper、resource manager 即使未公開，也必須有維護價值的 docstring。
- 任何業務規則、API contract mapping、資料一致性假設、效能取捨、相容性考量或特殊 edge case 必須註解說明。
- 刻意忽略 exception、使用 broad exception isolation、繞過 type checker/linter、使用動態 import/reflection 或非典型 resource lifecycle 時，必須註解原因。

### Docstring 最低審查標準

Public API 與重要 internal boundary 的 docstring 必須能回答與該 symbol
相關的問題。不是每個 symbol 都需要回答所有問題，但缺少 relevant
answer 時視為文件不足。

- Responsibility boundary：此 module/class/function 負責什麼，不負責什麼。
- Caller obligations：呼叫者必須提供什麼前置條件、權限、timeout、config、或 cleanup。
- Error semantics：會 raise 哪些 application/domain exception，哪些錯誤可重試，哪些錯誤代表認證、授權、設定或外部 API 失敗。
- Data consistency：是否讀寫 durable file、cache、config 或 credential store。
- Resource lifecycle：是否持有 file、socket、HTTP client、stream、timer、lock 或 subprocess，何時釋放。
- Compatibility and security：哪些行為是 API contract、CLI contract、credential/security boundary 或未來 migration 不能任意破壞的。

### Docstring 與註解寫法

- Docstring 必須使用三個雙引號 `"""`。
- Module docstring 應描述檔案內容與使用情境；測試檔只有在有特殊 setup、外部依賴或執行方式時才需要 module docstring。
- Docstring summary line 應是完整句子，並以句點、問號或驚嘆號結束。
- Function docstring 使用 Google style section：`Args:`、`Returns:`、`Yields:`、`Raises:`，只在需要補充 signature 無法表達的 contract 時撰寫。
- Class docstring 應描述 instance 代表的概念；public attribute 可用 `Attributes:` section 說明。
- Inline comment 用來說明 why、contract、assumption、edge case，不應描述 Python 讀者已能看懂的 what。
- 註解與 docstring 必須與程式碼同步更新；過期註解視為 bug。

```python
class ChatCompletionGateway(Protocol):
    """Sends chat completion requests through an outer-layer API adapter.

    Implementations own HTTP transport, authentication, timeout, retry, and
    response validation. Use cases depend on this protocol so they can be
    tested without opening sockets or loading user credentials.
    """

    def create_completion(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResult:
        """Creates a completion for an already validated application request.

        Raises:
            AuthenticationError: The configured credential was rejected.
            ProviderUnavailableError: The upstream API could not serve the
                request and the operation may be retried.
        """
```

## Type Annotations

- Public API、跨 layer boundary、stable data model、port/protocol 與 non-obvious helper 必須有 type annotations。
- 不要求所有 local variable 都標註型別；當型別難以推論、容易誤用或曾造成錯誤時才加上 annotated assignment。
- 缺值語意必須明確寫成 `X | None`，不得用 `value: X = None` 暗示 optional。
- 偏好 `collections.abc.Sequence`、`Mapping`、`Iterable` 等抽象容器作為 input type；需要具體資料結構語意時才使用 `list`、`dict`、`tuple`。
- Generic type 必須提供 type parameter；不要留下隱含 `Any` 的 `Mapping`、`Sequence` 或 `Callable`。
- `Any` 只能用在外部動態資料尚未驗證、第三方 typing 缺失或明確隔離邊界；使用時必須縮小 scope 並盡快 validation/narrowing。
- 複雜 type 可用具名 type alias 表達；public alias 使用 `CapWords`，internal alias 使用 `_CapWords`。
- Type-only imports 可放在 `if TYPE_CHECKING:` 中，但只在避免 runtime import cycle 或昂貴 import 時使用；循環 typing dependency 通常代表需要重整模組邊界。
- `typing.Text`、舊式 `typing.List`/`typing.Dict` 風格不應用於新程式碼；優先使用內建泛型與 `collections.abc`。

## Exceptions、Logging 與錯誤訊息

- Exceptions 是 Python 的錯誤通道，但必須保有清楚語意；不要用 magic return value 表示失敗。
- 使用 built-in exception 時必須符合語意，例如 precondition violation 可用 `ValueError`。
- Application/domain exception 應繼承合適的 existing exception class，名稱以 `Error` 結尾。
- 不使用 bare `except:`。只有在 re-raise 或 isolation boundary 需要記錄並隔離錯誤時，才可捕捉 broad exception，且必須註解原因。
- `try` block 範圍應盡量小，避免把非預期錯誤包進同一個 handler。
- 不使用 `assert` 進行 runtime validation 或 application logic；pytest 測試中的 `assert` 例外。
- Error message 必須精準描述實際錯誤條件，並讓插值內容可辨識、可搜尋。
- Logging API 若接受 pattern string，使用 literal pattern 與 lazy formatting，不用 f-string 先行格式化。
- 使用者可見錯誤訊息應描述可採取的下一步；credential、token、secret、raw authorization header 不得出現在使用者錯誤或 log 中。

## CLI、Config 與外部 I/O

- CLI command function 屬於 interface adapter 或 framework/driver，不應承載核心 domain rule。
- CLI option parsing、terminal formatting、stdout/stderr 寫入、exit code mapping 應在外層完成，再轉成 application input/output model。
- stdout 用於命令的主要結果；stderr 用於錯誤、警告、progress 或 diagnostic message。
- Exit code 語意必須穩定且可測試；不要讓 random exception traceback 成為一般使用者流程。
- Config file、environment variable 與 credential loading 屬於外層細節，不得直接散落在 use case 或 domain model。
- HTTP client、OpenAI-compatible SDK、streaming response、filesystem、subprocess、socket 等外部資源必須集中在 adapter/infrastructure，並以 port/protocol 連接內層。
- File、socket、HTTP client、stream、temporary directory 等 closeable resource 必須使用 context manager 或明確 lifecycle。若無法使用 context manager，docstring 或註解必須說明釋放責任。

## Python 語言使用

- Comprehension 只用於簡單清楚的 case；多個 `for` 或多層 filter expression 應改用一般 loop。
- 使用 container 的 default iterator 與 `in` / `not in`；不要呼叫不必要的 `.keys()` 或產生中間 list。
- 避免 mutable global state。若確實需要，必須放在 module level、以 `_` 標示 internal，並註解設計原因。
- Default argument 不得使用 mutable value；用 `None` sentinel 並在函式內建立新物件。
- Power features，例如自訂 metaclass、runtime bytecode、動態繼承、import hack、過度 reflection，只有在有清楚必要性時才可使用。
- Getter/setter 只有在取得或設定行為有實質成本、side effect 或 validation 時才使用；單純資料可直接公開 attribute 或使用 property。
- `main()` 與 executable entry point 必須避免 import 時執行副作用。可執行檔應使用 `if __name__ == "__main__":` guard。

## 測試規範

- 測試應驗證使用者可觀察行為、application contract 與錯誤語意，不只驗證 implementation detail。
- Domain model 與 use case 測試不得需要真實 terminal、network、config file、credential store 或 provider API。
- CLI 測試應涵蓋 arguments/options、stdout/stderr、exit code、user-facing error 與 config/credential edge cases。
- Adapter 測試應涵蓋 DTO/request/response mapping、exception mapping、timeout/retry/cancellation 語意與 resource cleanup。
- 測試名稱應描述行為差異；複雜案例可使用 table-driven style 或 parametrized tests。
- Test helper 應保持小而明確；若 helper 隱藏重要 assertion 或 side effect，需用 docstring 或註解說明。
- 測試資料與 setup 應限制在需要的 scope 內，避免跨測試共享可變狀態。

## Agent 執行規則

AI agent 修改 xclient Python 程式碼時必須遵守以下規則：

- 先閱讀鄰近 package 的既有風格，再進行修改。
- 新增 public API 或重要 internal boundary 時，必須同步新增有維護價值的 docstring。
- 修改 API contract mapping、exception semantics、typing boundary、resource lifecycle、CLI stdout/stderr 或 exit code 行為時，必須同步更新 docstring、測試與相關文件。
- 若程式碼需要複雜寫法，必須優先嘗試簡化；無法簡化時，用註解說明必要原因。
- 形式註解、identifier summary comment、只描述 `what` 的 comment 視為不符合規範；必須補足 contract、assumption、boundary 或 why。
- 新增 CLI command、use case、adapter、infrastructure、config/auth/token/security 相關程式碼時，必須確認 docstring 達到本文件最低審查標準。
- 不得用大量低價值註解填充；註解必須幫助未來讀者避免誤用或誤改。
- 完成修改前應執行或建議執行相關格式化、lint、type check 與測試。
