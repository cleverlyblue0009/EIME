
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.api.models import Invariant

SignalFn = Callable[[Dict[str, Any], Dict[str, Any], Dict[str, Any], set, List[str]], bool]


def _source(cfg: Dict[str, Any]) -> str:
    return cfg.get("source", "") if cfg else ""


def _has_any(source: str, needles: List[str]) -> bool:
    return any(needle in source for needle in needles)


def _has_all(source: str, needles: List[str]) -> bool:
    return all(needle in source for needle in needles)


def _has_var(var_names: set, names: List[str]) -> bool:
    return any(name in var_names for name in names)


def _uses_import(imports: List[str], name: str) -> bool:
    return any(name in imp for imp in imports)


def sig_var(*names: str) -> SignalFn:
    return lambda cfg, vdg, cg, vars, imps: _has_var(vars, list(names))


def sig_any(*tokens: str) -> SignalFn:
    return lambda cfg, vdg, cg, vars, imps: _has_any(_source(cfg), list(tokens))


def sig_all(*tokens: str) -> SignalFn:
    return lambda cfg, vdg, cg, vars, imps: _has_all(_source(cfg), list(tokens))


def sig_range_len_k(cfg, vdg, cg, vars, imps) -> bool:
    src = _source(cfg)
    return "range" in src and _has_any(src, ["range(len(", "len("]) and _has_any(src, ["- k", "-k"])


def sig_mid(cfg, vdg, cg, vars, imps) -> bool:
    src = _source(cfg)
    return _has_var(vars, ["mid"]) and _has_any(src, ["// 2", "//2", "(low+high)", "low + (high - low)"])


def sig_heapq(cfg, vdg, cg, vars, imps) -> bool:
    src = _source(cfg)
    return _uses_import(imps, "heapq") or _has_any(src, ["heappush", "heappop"])


def sig_deque(cfg, vdg, cg, vars, imps) -> bool:
    src = _source(cfg)
    return _uses_import(imps, "collections") or "deque" in src


def sig_recursion(cfg, vdg, cg, vars, imps) -> bool:
    for func, called in cg.get("calls", {}).items():
        if func in called:
            return True
    return False


def sig_dp(cfg, vdg, cg, vars, imps) -> bool:
    return _has_var(vars, ["dp", "memo", "cache"]) or _has_any(_source(cfg), ["dp[", "memo["])


def sig_union_find(cfg, vdg, cg, vars, imps) -> bool:
    src = _source(cfg)
    return _has_var(vars, ["parent", "rank", "size"]) and _has_any(src, ["find(", "union("])


def sig_trie(cfg, vdg, cg, vars, imps) -> bool:
    src = _source(cfg)
    return _has_any(src, ["Trie", "TrieNode", "children", "is_end", "startswith", "insert("])


def sig_graph(cfg, vdg, cg, vars, imps) -> bool:
    src = _source(cfg)
    return _has_any(src, ["graph", "adj", "neighbors"]) or _has_var(vars, ["graph", "adj", "edges"])


def sig_stack(cfg, vdg, cg, vars, imps) -> bool:
    return _has_var(vars, ["stack", "stk"]) or "stack" in _source(cfg)


def sig_queue(cfg, vdg, cg, vars, imps) -> bool:
    return _has_var(vars, ["queue", "q", "deque"]) or "queue" in _source(cfg)


def sig_sort(cfg, vdg, cg, vars, imps) -> bool:
    return _has_any(_source(cfg), ["sorted(", ".sort("])


@dataclass
class IntentPattern:
    name: str
    variant: str
    signals: List[Tuple[float, SignalFn]]
    invariants: List[Tuple[str, Optional[str], str]]
    pitfalls: List[str]
    role_hints: Dict[str, List[str]]
    loop_count_formula: Optional[str] = None

    def match(
        self,
        cfg: Dict[str, Any],
        vdg: Dict[str, Any],
        call_graph: Dict[str, Any],
        var_names: set,
        imports: List[str],
    ) -> float:
        score = 0.0
        for weight, predicate in self.signals:
            try:
                if predicate(cfg, vdg, call_graph, var_names, imports):
                    score += weight
            except Exception:
                continue
        return min(score, 1.0)

    def get_invariants(self, var_role_map: Dict[str, Any]) -> List[Invariant]:
        invariants: List[Invariant] = []
        for desc, expr, criticality in self.invariants:
            invariants.append(
                Invariant(
                    description=desc,
                    formal_expression=expr,
                    criticality=criticality,
                    holds_at=["loop", "iteration"],
                )
            )
        return invariants

    def get_expected_loop_count(self, n: Any, k: Any = None) -> Dict[str, str]:
        if self.loop_count_formula:
            return {"main_loop": self.loop_count_formula}
        return {}

    def get_known_pitfalls(self) -> List[str]:
        return list(self.pitfalls)

    def get_variable_role_hints(self) -> Dict[str, List[str]]:
        return dict(self.role_hints)


PATTERNS: List[Dict[str, Any]] = []


class PatternRegistry:
    def __init__(self) -> None:
        if not PATTERNS:
            _init_patterns()
        self.patterns: Dict[str, IntentPattern] = {
            p["name"]: IntentPattern(**p) for p in PATTERNS
        }

    def get_pattern(self, name: str) -> IntentPattern | None:
        return self.patterns.get(name)

    def score_all(self, cfg, vdg, call_graph, var_names, imports) -> List[Tuple[IntentPattern, float]]:
        scores: List[Tuple[IntentPattern, float]] = []
        for pattern in self.patterns.values():
            score = pattern.match(cfg, vdg, call_graph, var_names, imports)
            scores.append((pattern, score))
        scores.sort(key=lambda item: item[1], reverse=True)
        return scores

    def best_pattern(self, cfg, vdg, call_graph, var_names, imports) -> Tuple[IntentPattern, float]:
        scores = self.score_all(cfg, vdg, call_graph, var_names, imports)
        if not scores:
            raise ValueError("No patterns registered")
        return scores[0]


def _init_patterns() -> None:
    if PATTERNS:
        return

    PATTERNS.extend([
        {
            "name": "sliding_window_fixed",
            "variant": "fixed_size",
            "signals": [
                (0.3, sig_range_len_k),
                (0.2, sig_var("k", "window_size")),
                (0.2, sig_var("left", "right")),
                (0.15, sig_any("window_sum", "curr_sum", "i + k", "i+k")),
                (0.15, sig_any("max_sum", "result", "ans")),
                (0.15, sig_any("+=", "-=")),
            ],
            "invariants": [
                ("right - left == k at all times inside loop", "right - left == k", "HIGH"),
                ("result must be updated on every window position", None, "MEDIUM"),
                ("loop must execute len(arr) - k + 1 times total", None, "HIGH"),
            ],
            "pitfalls": [
                "range(len(arr)-k) skips last window — must be range(len(arr)-k+1)",
                "initializing window sum inside loop instead of before is O(n*k) not O(n)",
            ],
            "role_hints": {"left": ["WINDOW_START"], "right": ["WINDOW_END"], "k": ["LOOP_COUNTER"]},
            "loop_count_formula": "len(arr) - k + 1",
        },
        {
            "name": "sliding_window_variable",
            "variant": "variable_size",
            "signals": [
                (0.25, sig_any("while", "for")),
                (0.3, sig_var("left", "right")),
                (0.2, sig_any(">=", "<=", "sum", "len(")),
                (0.15, sig_var("left", "right")),
                (0.1, sig_any("max", "min", "result")),
            ],
            "invariants": [
                ("left <= right at all times", "left <= right", "HIGH"),
                ("window always represents a valid subarray", None, "MEDIUM"),
                ("both pointers advance at most 2n times", None, "LOW"),
            ],
            "pitfalls": [
                "shrink condition should be >= not >, or vice versa depending on problem",
                "not updating result after final shrink",
            ],
            "role_hints": {"left": ["WINDOW_START"], "right": ["WINDOW_END"]},
        },
        {
            "name": "two_pointer_opposite",
            "variant": "opposite_ends",
            "signals": [
                (0.35, sig_var("left", "right")),
                (0.25, sig_any("left < right", "while left < right")),
                (0.25, sig_any("left +=", "right -=", "left-=", "right+=")),
                (0.15, sig_any("arr[left]", "arr[right]")),
            ],
            "invariants": [
                ("left < right invariant must hold at loop entry", "left < right", "HIGH"),
                ("both pointers advance on each iteration", None, "MEDIUM"),
            ],
            "pitfalls": [
                "using left <= right causes processing center element twice",
                "not handling the case where both pointers should advance",
            ],
            "role_hints": {"left": ["POINTER_LEFT"], "right": ["POINTER_RIGHT"]},
        },
        {
            "name": "two_pointer_same_direction",
            "variant": "same_direction",
            "signals": [
                (0.3, sig_var("slow", "fast")),
                (0.2, sig_any("for", "while")),
                (0.25, sig_any("slow +=", "slow =")),
                (0.25, sig_any("arr[slow]", "nums[slow]")),
            ],
            "invariants": [
                ("fast >= slow at all times", "fast >= slow", "HIGH"),
                ("arr[0..slow-1] contains the valid result", None, "MEDIUM"),
            ],
            "pitfalls": [
                "slow should start at 1 when keeping first element",
                "off-by-one in final return (return slow vs slow+1)",
            ],
            "role_hints": {"slow": ["SLOW_POINTER"], "fast": ["FAST_POINTER"]},
        },
        {
            "name": "binary_search_array",
            "variant": "array",
            "signals": [
                (0.25, sig_var("low", "high")),
                (0.3, sig_mid),
                (0.2, sig_any("low <= high", "low < high")),
                (0.25, sig_any("mid+1", "mid-1", "mid + 1", "mid - 1")),
            ],
            "invariants": [
                ("answer always in [low, high] range", None, "HIGH"),
                ("search space shrinks each iteration", None, "MEDIUM"),
            ],
            "pitfalls": [
                "mid+1/mid-1 vs mid causes infinite loop",
                "low <= high vs low < high determines if single element is checked",
                "wrong half eliminated when target equals arr[mid]",
            ],
            "role_hints": {"low": ["LEFT_BOUND"], "high": ["RIGHT_BOUND"], "mid": ["MID_POINTER"]},
        },
    ])
    PATTERNS.extend([
        {
            "name": "binary_search_answer_space",
            "variant": "answer_space",
            "signals": [
                (0.25, sig_mid),
                (0.25, sig_any("feasible", "can(", "possible(")),
                (0.3, sig_any("if", "else")),
                (0.2, sig_any("low =", "high =")),
            ],
            "invariants": [
                ("answer space must be monotone in feasibility", None, "HIGH"),
            ],
            "pitfalls": [
                "feasibility function incorrect for boundary values",
                "wrong convergence condition (off by one on final answer)",
            ],
            "role_hints": {"low": ["LEFT_BOUND"], "high": ["RIGHT_BOUND"], "mid": ["MID_POINTER"]},
        },
        {
            "name": "merge_sort",
            "variant": "top_down",
            "signals": [
                (0.2, sig_recursion),
                (0.3, sig_any("merge", "mid")),
                (0.3, sig_any("[:mid]", "[mid:", "left", "right")),
                (0.2, sig_any("return", "if len(")),
            ],
            "invariants": [
                ("left subarray is sorted before merge", None, "HIGH"),
                ("right subarray is sorted before merge", None, "HIGH"),
                ("merge produces sorted result of size (hi-lo+1)", None, "MEDIUM"),
            ],
            "pitfalls": [
                "mid = (lo+hi)//2 vs mid = lo + (hi-lo)//2 (overflow in other langs)",
                "merge uses < not <= causing instability",
                "off by one: right half should start at mid+1 not mid",
            ],
            "role_hints": {},
        },
        {
            "name": "quick_sort_lomuto",
            "variant": "lomuto",
            "signals": [
                (0.3, sig_any("pivot", "partition")),
                (0.3, sig_any("pivot", "lo", "hi")),
                (0.2, sig_any("i =", "j in range")),
                (0.2, sig_any("swap", "arr[i]", "arr[j]")),
            ],
            "invariants": [
                ("arr[lo..i] <= pivot after partition", None, "HIGH"),
                ("arr[i+1..hi] >= pivot after partition", None, "HIGH"),
            ],
            "pitfalls": [
                "comparing arr[j] < pivot vs arr[j] <= pivot affects equal elements",
                "not handling already-sorted input (O(n²) worst case)",
            ],
            "role_hints": {},
        },
        {
            "name": "heap_top_k",
            "variant": "top_k",
            "signals": [
                (0.2, sig_heapq),
                (0.3, sig_any("heappush", "heappop")),
                (0.3, sig_any("size", "len(", "> k", ">k")),
                (0.2, sig_any("heap[0]", "heappop")),
            ],
            "invariants": [
                ("heap size never exceeds k", None, "HIGH"),
                ("heap root is always the k-th element seen", None, "MEDIUM"),
            ],
            "pitfalls": [
                "using max-heap for top-k-smallest (need min-heap)",
                "not popping when heap exceeds k before pushing",
                "returning heap[0] vs heappop (same for 1 element, differs for k>1)",
            ],
            "role_hints": {"heap": ["HEAP_DS"]},
        },
        {
            "name": "heap_merge_k_lists",
            "variant": "merge_k_lists",
            "signals": [
                (0.3, sig_heapq),
                (0.3, sig_any("list", "lists", "idx")),
                (0.3, sig_any("heappush", "heappop")),
                (0.1, sig_any("result", "merged")),
            ],
            "invariants": [
                ("heap always contains at most k elements", None, "HIGH"),
                ("popped element is globally minimum", None, "HIGH"),
            ],
            "pitfalls": [
                "not including list index in heap element causes wrong list advance",
                "not checking if next element exists before pushing",
            ],
            "role_hints": {"heap": ["HEAP_DS"]},
        },
    ])
    PATTERNS.extend([
        {
            "name": "bfs_standard",
            "variant": "standard",
            "signals": [
                (0.25, sig_deque),
                (0.2, sig_queue),
                (0.2, sig_var("visited")),
                (0.2, sig_any("for neighbor", "neighbors")),
                (0.15, sig_any("append", "popleft")),
            ],
            "invariants": [
                ("visited never re-enqueues a node", None, "HIGH"),
                ("shortest path correct only if visited marked before enqueue", None, "HIGH"),
            ],
            "pitfalls": [
                "marking visited after dequeue instead of before enqueue (wastes work, wrong levels)",
                "not initializing start node as visited before enqueue",
            ],
            "role_hints": {"queue": ["QUEUE_DS"], "visited": ["VISITED_SET"]},
        },
        {
            "name": "bfs_level_order",
            "variant": "level_order",
            "signals": [
                (0.3, sig_deque),
                (0.3, sig_any("level", "len(queue)")),
                (0.2, sig_any("for _ in range", "range(level_size)")),
                (0.2, sig_any("append", "popleft")),
            ],
            "invariants": [
                ("inner loop processes exactly len(queue) nodes at entry", None, "HIGH"),
                ("all nodes at depth d processed before any at depth d+1", None, "HIGH"),
            ],
            "pitfalls": ["capturing queue size after inner loop starts changes level boundary"],
            "role_hints": {"queue": ["QUEUE_DS"]},
        },
        {
            "name": "dfs_recursive",
            "variant": "recursive",
            "signals": [
                (0.3, sig_recursion),
                (0.2, sig_var("visited")),
                (0.2, sig_any("if not", "return")),
                (0.15, sig_any("append", "pop")),
                (0.15, sig_any("for neighbor", "dfs(")),
            ],
            "invariants": [
                ("visited check before recursion prevents revisiting", None, "HIGH"),
                ("backtrack restores state exactly as before recursive call", None, "MEDIUM"),
            ],
            "pitfalls": [
                "forgetting visited.remove() in backtracking problems",
                "modifying visited before vs after processing affects path finding",
            ],
            "role_hints": {"visited": ["VISITED_SET"]},
        },
        {
            "name": "dfs_iterative",
            "variant": "iterative",
            "signals": [
                (0.3, sig_stack),
                (0.25, sig_any("pop(", "append(")),
                (0.2, sig_var("visited")),
                (0.25, sig_any("while", "stack")),
            ],
            "invariants": [
                ("LIFO order of stack matches recursive DFS order", None, "MEDIUM"),
            ],
            "pitfalls": ["checking visited on push vs pop gives different behavior"],
            "role_hints": {"stack": ["STACK_DS"]},
        },
        {
            "name": "dp_1d_linear",
            "variant": "linear",
            "signals": [
                (0.2, sig_dp),
                (0.2, sig_any("dp[0]", "dp[1]")),
                (0.35, sig_any("dp[i-1]", "dp[i - 1]")),
                (0.15, sig_any("for i in range")),
                (0.1, sig_any("return dp")),
            ],
            "invariants": [
                ("dp[i] represents optimal solution for subproblem of size i", None, "HIGH"),
                ("all dp[j] for j < i are computed before dp[i]", None, "MEDIUM"),
            ],
            "pitfalls": [
                "dp array of size n instead of n+1 causes index out of bounds",
                "returning dp[n-1] instead of dp[n]",
                "wrong base case (dp[0] should be 0 vs 1 depending on problem)",
            ],
            "role_hints": {"dp": ["DP_TABLE"]},
        },
        {
            "name": "dp_1d_kadane",
            "variant": "kadane",
            "signals": [
                (0.3, sig_var("current_sum", "max_sum")),
                (0.35, sig_any("max(")),
                (0.2, sig_any("current_sum", "max_sum")),
                (0.15, sig_any("arr[0]", "-inf")),
            ],
            "invariants": [
                ("current_sum represents max subarray ending at current position", None, "HIGH"),
                ("max_sum is global maximum seen so far", None, "HIGH"),
            ],
            "pitfalls": [
                "initializing to 0 fails for all-negative arrays",
                "using max(0, ...) loses the negative-only case",
            ],
            "role_hints": {"current_sum": ["ACCUMULATOR"], "max_sum": ["RESULT_CANDIDATE"]},
        },
        {
            "name": "dp_2d_grid",
            "variant": "grid",
            "signals": [
                (0.25, sig_dp),
                (0.35, sig_any("dp[i-1][j]", "dp[i][j-1]")),
                (0.25, sig_any("for i in range", "for j in range")),
                (0.15, sig_any("first row", "first column")),
            ],
            "invariants": [
                ("dp[i][j] depends only on cells above and to the left", None, "HIGH"),
                ("boundary cells must be initialized before inner loops", None, "MEDIUM"),
            ],
            "pitfalls": [
                "wrong boundary: dp[m+1][n+1] vs dp[m][n] shifts all indices",
                "not initializing first row and column to 0",
            ],
            "role_hints": {"dp": ["DP_TABLE"]},
        },
        {
            "name": "dp_lcs",
            "variant": "lcs",
            "signals": [
                (0.3, sig_dp),
                (0.4, sig_any("dp[i-1][j-1] + 1", "==")),
                (0.3, sig_any("max(dp[i-1][j]", "dp[i][j-1]")),
            ],
            "invariants": [
                ("dp[i][j] = LCS length of s1[0..i-1] and s2[0..j-1]", None, "HIGH"),
            ],
            "pitfalls": ["comparing s1[i] vs s1[i-1] off by one in 1-indexed dp"],
            "role_hints": {"dp": ["DP_TABLE"]},
        },
        {
            "name": "dp_knapsack_01",
            "variant": "knapsack_01",
            "signals": [
                (0.25, sig_dp),
                (0.35, sig_any("for w in range", "capacity")),
                (0.3, sig_any("dp[w]", "dp[w-wt]", "val")),
                (0.1, sig_any("items", "weights")),
            ],
            "invariants": [
                ("reverse capacity iteration prevents using item twice", None, "HIGH"),
                ("dp[w] represents max value achievable with weight <= w", None, "MEDIUM"),
            ],
            "pitfalls": [
                "iterating capacity forward allows using same item multiple times (becomes unbounded knapsack)",
            ],
            "role_hints": {"dp": ["DP_TABLE"]},
        },
        {
            "name": "dp_edit_distance",
            "variant": "edit_distance",
            "signals": [
                (0.3, sig_dp),
                (0.25, sig_any("dp[i-1][j]", "dp[i][j-1]")),
                (0.35, sig_any("+ 1", "min(")),
                (0.1, sig_any("dp[0][j]", "dp[i][0]")),
            ],
            "invariants": [
                ("dp[i][j] is minimum operations to transform s1[:i] to s2[:j]", None, "HIGH"),
            ],
            "pitfalls": [],
            "role_hints": {"dp": ["DP_TABLE"]},
        },
    ])
    PATTERNS.extend([
        {
            "name": "tree_traversal",
            "variant": "traversal",
            "signals": [
                (0.2, sig_recursion),
                (0.3, sig_any("node.left", "node.right")),
                (0.2, sig_any("if not node", "if node is None")),
                (0.3, sig_any("preorder", "inorder", "postorder")),
            ],
            "invariants": [
                ("base case handles None node (leaf children)", None, "HIGH"),
                ("traversal visits every node exactly once", None, "HIGH"),
            ],
            "pitfalls": [
                "checking node.left and node.right instead of node being None",
                "in-order requires left → process → right, not left → right → process",
            ],
            "role_hints": {},
        },
        {
            "name": "tree_dp",
            "variant": "tree_dp",
            "signals": [
                (0.25, sig_recursion),
                (0.25, sig_any("global", "nonlocal", "max_sum")),
                (0.3, sig_any("left", "right")),
                (0.2, sig_any("return", "+")),
            ],
            "invariants": [
                ("left and right subtree values computed before combining", None, "HIGH"),
                ("global max updated with cross-root path, return value is one-sided", None, "MEDIUM"),
            ],
            "pitfalls": [
                "returning left+right (cross-path) instead of max(left,right)+1 (single path)",
            ],
            "role_hints": {},
        },
        {
            "name": "monotonic_stack",
            "variant": "mono_stack",
            "signals": [
                (0.3, sig_stack),
                (0.3, sig_any("while stack", "pop(")),
                (0.2, sig_any("next greater", "previous smaller")),
                (0.2, sig_any("indices", "index")),
            ],
            "invariants": [
                ("stack is always monotonically increasing or decreasing", None, "HIGH"),
                ("elements popped when they find their next greater/smaller", None, "MEDIUM"),
            ],
            "pitfalls": [
                "storing values instead of indices loses position info",
                "wrong comparison direction inverts monotonic property",
            ],
            "role_hints": {"stack": ["MONOTONIC_STACK"]},
        },
        {
            "name": "monotonic_queue",
            "variant": "mono_queue",
            "signals": [
                (0.25, sig_deque),
                (0.25, sig_any("popleft", "append")),
                (0.25, sig_any("window", "k")),
                (0.25, sig_any("max", "deque[0]")),
            ],
            "invariants": [
                ("front index always within current window", None, "HIGH"),
                ("deque values are decreasing", None, "MEDIUM"),
            ],
            "pitfalls": ["storing values not indices makes range-checking impossible"],
            "role_hints": {"deque": ["MONOTONIC_QUEUE"]},
        },
        {
            "name": "union_find",
            "variant": "union_find",
            "signals": [
                (0.25, sig_union_find),
                (0.3, sig_any("parent", "rank", "size")),
                (0.25, sig_any("find", "union")),
                (0.2, sig_any("path compression", "rank")),
            ],
            "invariants": [
                ("find(x) always returns root of x's component", None, "HIGH"),
                ("path compression points directly to root", None, "MEDIUM"),
            ],
            "pitfalls": [
                "not using path compression makes union-find O(n) not O(α(n))",
                "union without rank can create linear chains",
            ],
            "role_hints": {"parent": ["UNION_FIND_PARENT"]},
        },
        {
            "name": "trie_insert_search",
            "variant": "trie",
            "signals": [
                (0.3, sig_trie),
                (0.3, sig_any("children", "is_end")),
                (0.2, sig_any("insert", "search")),
                (0.2, sig_any("for ch in", "for c in")),
            ],
            "invariants": [
                ("every prefix of inserted word exists in trie", None, "HIGH"),
                ("is_end only True at word boundaries", None, "HIGH"),
            ],
            "pitfalls": [
                "not setting is_end=True after insert loop",
                "startsWith should NOT check is_end",
            ],
            "role_hints": {"node": ["TRIE_NODE"]},
        },
        {
            "name": "dijkstra",
            "variant": "dijkstra",
            "signals": [
                (0.3, sig_heapq),
                (0.2, sig_graph),
                (0.3, sig_any("dist", "distance")),
                (0.2, sig_any("if dist", "relax")),
            ],
            "invariants": [
                ("dist[v] is always shortest known distance to v", None, "HIGH"),
                ("once popped from heap, dist[v] is finalized", None, "HIGH"),
            ],
            "pitfalls": [
                "not checking if popped distance is stale (dist[u] < d)",
                "using negative edge weights (Dijkstra is incorrect then)",
            ],
            "role_hints": {"dist": ["DISTANCE_MAP"], "heap": ["HEAP_DS"]},
        },
        {
            "name": "topological_sort_kahn",
            "variant": "kahn",
            "signals": [
                (0.3, sig_any("in_degree", "indegree")),
                (0.25, sig_queue),
                (0.25, sig_any("for neighbor", "graph")),
                (0.2, sig_any("append", "popleft")),
            ],
            "invariants": [
                ("node processed only when all predecessors processed", None, "HIGH"),
                ("cycle exists iff queue empties before processing all nodes", None, "MEDIUM"),
            ],
            "pitfalls": [
                "not detecting cycle (result length check)",
                "building graph in wrong direction",
            ],
            "role_hints": {"in_degree": ["IN_DEGREE"]},
        },
        {
            "name": "backtracking",
            "variant": "backtracking",
            "signals": [
                (0.25, sig_recursion),
                (0.2, sig_any("path", "current_path")),
                (0.2, sig_any("append", "pop")),
                (0.35, sig_any("backtrack", "dfs")),
            ],
            "invariants": [
                ("state fully restored after each recursive call", None, "HIGH"),
                ("pruning condition checked before recursion", None, "MEDIUM"),
            ],
            "pitfalls": [
                "appending path reference not copy: results.append(path) vs results.append(path[:])",
                "missing backtrack step (not removing added choice)",
            ],
            "role_hints": {"path": ["STACK_DS"]},
        },
        {
            "name": "interval_merge",
            "variant": "interval_merge",
            "signals": [
                (0.3, sig_sort),
                (0.3, sig_any("interval", "start", "end")),
                (0.25, sig_any("max(end", "<=")),
                (0.15, sig_any("merged", "result")),
            ],
            "invariants": [
                ("intervals must be sorted before merging", None, "HIGH"),
                ("merge condition: curr.start <= prev.end", None, "HIGH"),
            ],
            "pitfalls": [
                "using < instead of <= misses touching intervals",
                "not sorting before merging",
            ],
            "role_hints": {},
        },
        {
            "name": "recursion_memo",
            "variant": "top_down",
            "signals": [
                (0.35, sig_recursion),
                (0.25, sig_any("memo", "cache", "@lru_cache")),
                (0.2, sig_any("if n <= 1", "if n == 0", "if n == 1", "if not node")),
                (0.2, sig_any("return", "+", "max(", "min(")),
            ],
            "invariants": [
                ("recursive calls must reduce the problem state", None, "HIGH"),
                ("base cases must terminate the smallest subproblems", None, "HIGH"),
                ("memo must be checked before expanding the same state twice", None, "MEDIUM"),
            ],
            "pitfalls": [
                "missing memo check before recursion",
                "wrong base case value poisons every parent state",
                "recursive call does not reduce the input size",
            ],
            "role_hints": {"memo": ["MEMO_TABLE"], "cache": ["MEMO_TABLE"]},
        },
        {
            "name": "graph_mst",
            "variant": "kruskal_or_prim",
            "signals": [
                (0.3, sig_graph),
                (0.25, sig_any("edge", "edges", "weight")),
                (0.25, sig_any("union(", "find(", "parent")),
                (0.2, sig_any("sorted(", ".sort(", "heapq")),
            ],
            "invariants": [
                ("selected edges must connect new components without creating cycles", None, "HIGH"),
                ("edge or frontier selection must be driven by minimum weight", None, "HIGH"),
            ],
            "pitfalls": [
                "sorting edges without unioning accepted components",
                "using the wrong sort key instead of edge weight",
                "forgetting to skip edges that create cycles",
            ],
            "role_hints": {"parent": ["UNION_FIND_PARENT"], "edges": ["GRAPH_ADJ"]},
        },
        {
            "name": "matrix_traversal",
            "variant": "boundary_traversal",
            "signals": [
                (0.3, sig_any("top", "bottom", "left", "right")),
                (0.25, sig_any("matrix", "grid")),
                (0.25, sig_any("while top", "while left", "for row", "for col")),
                (0.2, sig_any("top +=", "bottom -=", "left +=", "right -=")),
            ],
            "invariants": [
                ("active boundaries must move inward after each directional pass", None, "HIGH"),
                ("each cell should be visited at most once", None, "HIGH"),
            ],
            "pitfalls": [
                "forgetting to shrink one boundary repeats cells",
                "direction changes without boundary updates can create infinite loops",
            ],
            "role_hints": {"top": ["LEFT_BOUND"], "bottom": ["RIGHT_BOUND"]},
        },
    ])
