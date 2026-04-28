import pickle
from typing import Callable, Dict, Any, Optional, List, Tuple

END = "END"

class GraphCompileError(Exception):
    pass

class StateGraph:
    def __init__(self, state_type: Optional[type] = None):
        self.state_type = state_type
        self.nodes: Dict[str, Callable] = {}
        self.edges: Dict[str, List[str]] = {}
        self.cond_edges: Dict[str, Tuple[Callable, Dict[str, str]]] = {}
        self.entry_point: Optional[str] = None

    def add_node(self, name: str, func: Callable):
        self.nodes[name] = func
        self.edges.setdefault(name, [])

    def set_entry_point(self, name: str):
        self.entry_point = name

    def add_edge(self, src: str, dst: str):
        self.edges.setdefault(src, []).append(dst)

    def add_conditional_edges(self, node: str, router_func: Callable, mapping: Dict[str, str]):
        self.cond_edges[node] = (router_func, mapping)

    def compile(self, checkpointer=None, interrupt_before: Optional[List[str]] = None):
        return GraphRunner(self, checkpointer=checkpointer, interrupt_before=(interrupt_before or []))


class GraphRunner:
    def __init__(self, graph: StateGraph, checkpointer=None, interrupt_before: Optional[List[str]] = None):
        self.graph = graph
        self.checkpointer = checkpointer
        self.interrupt_before = set(interrupt_before or [])

    def _save_checkpoint(self, thread_id: str, state: dict, current_node: Optional[str]):
        if self.checkpointer:
            self.checkpointer.save(thread_id, state, current_node)

    def _load_checkpoint(self, thread_id: str):
        if self.checkpointer:
            return self.checkpointer.load(thread_id)
        return None, None

    def stream(self, initial_state: Optional[dict], config: Optional[dict] = None):
        cfg = config or {}
        thread_id = cfg.get("configurable", {}).get("thread_id", "default_thread")
        # resume or start
        if initial_state is None:
            loaded_state, current_node = self._load_checkpoint(thread_id)
            if loaded_state is None:
                raise RuntimeError(f"No checkpoint for thread_id={thread_id}")
            state = loaded_state
            resumed = True
        else:
            state = dict(initial_state)
            current_node = self.graph.entry_point
            self._save_checkpoint(thread_id, state, current_node)
            resumed = False

        # Execution loop
        while current_node and current_node != END:
            # If current node is in interrupt_before, pause execution BEFORE running it (only on fresh runs).
            if current_node in self.interrupt_before and not resumed:
                # save checkpoint and pause; caller may resume later with initial_state=None
                self._save_checkpoint(thread_id, state, current_node)
                return
            if current_node not in self.graph.nodes:
                raise GraphCompileError(f"Node '{current_node}' is not registered.")
            node_func = self.graph.nodes[current_node]
            try:
                result = node_func(state)
            except Exception as e:
                result = {"execution_errors": state.get("execution_errors", []) + [repr(e)]}
            # merge result into state (simple strategy)
            if isinstance(result, dict):
                for k, v in result.items():
                    if isinstance(state.get(k), list) and isinstance(v, list):
                        state[k] = state.get(k, []) + v
                    else:
                        state[k] = v
            # decide next node
            if current_node in self.graph.cond_edges:
                router, mapping = self.graph.cond_edges[current_node]
                key = router(state)
                next_node = mapping.get(key)
                if next_node is None:
                    raise GraphCompileError(f"Router returned unknown key '{key}'.")
            else:
                nexts = self.graph.edges.get(current_node, [])
                next_node = nexts[0] if nexts else END
            # save checkpoint (next node)
            self._save_checkpoint(thread_id, state, next_node)
            # yield event for completed node
            yield {current_node: dict(state)}
            current_node = next_node
        # finished
        self._save_checkpoint(thread_id, state, None)
        yield {END: dict(state)}

    def get_state(self, config: Optional[dict] = None):
        cfg = config or {}
        thread_id = cfg.get("configurable", {}).get("thread_id", "default_thread")
        state, current_node = self._load_checkpoint(thread_id)
        class S: pass
        s = S()
        s.values = state or {}
        s.current_node = current_node
        return s
