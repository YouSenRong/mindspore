# This is the Python adaptation and derivative work of Myia (https://github.com/mila-iqia/myia/).
#
# Copyright 2020 Huawei Technologies Co., Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================

"""Basic composite operations."""
from functools import partial
from types import FunctionType

from mindspore import context
from ..._c_expression import EnvInstance_, GradOperation_, HyperMap_, Map_, MultitypeFuncGraph_, Tail_, \
                             TupleAdd_, TupleSlice_, UnpackCall_, ZipOperation_, ListAppend_, TupleGetItemTensor_
from ...common import dtype as mstype
from ...common.api import ms_function, _pynative_exec, _wrap_func
from .. import functional as F
from ...common.parameter import Parameter
from ...common.tensor import Tensor


__all__ = [EnvInstance_, TupleAdd_, TupleSlice_, UnpackCall_, TupleGetItemTensor_]


def add_flags(fn=None, **flags):
    """
    An decorator to add flag for a function.

    Note:
        Only supports bool value.

    Args:
        fn (Function): Function or cell to add flag. Default: None.
        flags (dict): Flags use kwargs. Default: None.

    Returns:
        Function, the fn added flags.

    Examples:
        >>> add_flags(net, predit=True)
    """
    def deco(fn):
        # need set the attr and access on c++
        if not hasattr(fn, "_mindspore_flags"):
            fn._mindspore_flags = {}

        fn._mindspore_flags.update({**flags})
        return fn
    ret = deco
    if fn is not None:
        ret = deco(fn)
    return ret


def core(fn=None, **flags):
    """
    A decorator to add flag to a function.

    By default, the function is marked core=True using this decorator to
    set flag to a graph.

    Args:
        fn (Function): Function to add flag. Default: None.
        flags (dict): The following flags can be set core, which indicates that this is a core function or
                      other flag. Default: None.
    """
    # need set the attr and access on c++

    def deco(fn):
        fn._mindspore_flags = {
            'core': True,
            **flags,
        }
        return fn

    if fn is not None:
        ret = deco(fn)
    else:
        ret = deco
    return ret


class GradOperation(GradOperation_):
    """
    An higher-order function which is used to generate the gradient function for the input function.

    The gradient function generated by `GradOperation` higher-order function can be customized by construction args.

    Given an input function `net = Net()` that take `x` and `y` as inputs, and has a parameter `z`,
    see `Net` in Examples.

    To generate a gradient function that returns gradients with respect to the first input
    (see `GradNetWrtX` in Examples).

        1. Construct a `GradOperation` higher-order function with default arguments:
           `grad_op = GradOperation()`.

        2. Call it with input function as argument to get the gradient function: `gradient_function = grad_op(net)`.

        3. Call the gradient function with input function's inputs to get the gradients with respect to the first input:
           `grad_op(net)(x, y)`.

    To generate a gradient function that returns gradients with respect to all inputs (see `GradNetWrtXY` in Examples).

        1. Construct a `GradOperation` higher-order function with `get_all=True` which
           indicates getting gradients with respect to all inputs, they are `x` and `y` in example function `Net()`:
           `grad_op = GradOperation(get_all=True)`.

        2. Call it with input function as argument to get the gradient function: `gradient_function = grad_op(net)`.

        3. Call the gradient function with input function's inputs to get the gradients with respect to all inputs:
           `gradient_function(x, y)`.

    To generate a gradient function that returns gradients with respect to given parameters
    (see `GradNetWithWrtParams` in Examples).

        1. Construct a `GradOperation` higher-order function with `get_by_list=True`:
           `grad_op = GradOperation(get_by_list=True)`.

        2. Construct a `ParameterTuple` that will be passed along input function when constructing
           `GradOperation` higher-order function, it will be used as a parameter filter that determine
           which gradient to return: `params = ParameterTuple(net.trainable_params())`.

        3. Call it with input function and `params` as arguments to get the gradient function:
           `gradient_function = grad_op(net, params)`.

        4. Call the gradient function with input function's inputs to get the gradients with
        respect to given parameters: `gradient_function(x, y)`.

    To generate a gradient function that returns gradients with respect to all inputs and given parameters
    in the format of ((dx, dy), (dz))(see `GradNetWrtInputsAndParams` in Examples).

        1. Construct a `GradOperation` higher-order function with `get_all=True` and `get_by_list=True`:
           `grad_op = GradOperation(get_all=True, get_by_list=True)`.

        2. Construct a `ParameterTuple` that will be passed along input function when constructing
           `GradOperation` higher-order function: `params = ParameterTuple(net.trainable_params())`.

        3. Call it with input function and `params` as arguments to get the gradient function:
           `gradient_function = grad_op(net, params)`.

        4. Call the gradient function with input function's inputs
           to get the gradients with respect to all inputs and given parameters: `gradient_function(x, y)`.

    We can configure the sensitiviy(gradient with respect to output) by setting `sens_param=True` and
    passing in an extra sensitiviy input to the gradient function, the sensitiviy input should be
    with same shape and type with input function's output(see `GradNetWrtXYWithSensParam` in Examples).

        1. Construct a `GradOperation` higher-order function with `get_all=True` and `sens_param=True`:
           `grad_op = GradOperation(get_all=True, sens_param=True)`.

        2. Define grad_wrt_output as sens_param which works as the gradient with respect to output:
           `grad_wrt_output = Tensor(np.ones([2, 2]).astype(np.float32))`.

        3. Call it with input function as argument to get the gradient function:
           `gradient_function = grad_op(net)`.

        4. Call the gradient function with input function's inputs and sens_param to
           get the gradients with respect to all inputs:
           `gradient_function(x, y, grad_wrt_output)`.

    Args:
        get_all (bool): If True, get all the gradients with respect to inputs. Default: False.
        get_by_list (bool): If True, get all the gradients with respect to Parameter variables.
            If get_all and get_by_list are both False, get the gradient with respect to first input.
            If get_all and get_by_list are both True, get the gradients with respect to inputs and Parameter variables
            at the same time in the form of ((gradients with respect to inputs),
            (gradients with respect to parameters)). Default: False.
        sens_param (bool): Whether append sensitivity(gradient with respect to output) as input. If sens_param is False,
            a 'ones_like(outputs)' sensitivity will be attached automatically. Default: False.

    Returns:
        The higher-order function which takes a function as argument and returns gradient function for it.

    Examples:
        >>> class Net(nn.Cell):
        >>>     def __init__(self):
        >>>         super(Net, self).__init__()
        >>>         self.matmul = P.MatMul()
        >>>         self.z = Parameter(Tensor(np.array([1.0], np.float32)), name='z')
        >>>     def construct(self, x, y):
        >>>         x = x * self.z
        >>>         out = self.matmul(x, y)
        >>>         return out
        >>>
        >>> class GradNetWrtX(nn.Cell):
        >>>     def __init__(self, net):
        >>>         super(GradNetWrtX, self).__init__()
        >>>         self.net = net
        >>>         self.grad_op = GradOperation()
        >>>     def construct(self, x, y):
        >>>         gradient_function = self.grad_op(self.net)
        >>>         return gradient_function(x, y)
        >>>
        >>> x = Tensor([[0.5, 0.6, 0.4], [1.2, 1.3, 1.1]], dtype=mstype.float32)
        >>> y = Tensor([[0.01, 0.3, 1.1], [0.1, 0.2, 1.3], [2.1, 1.2, 3.3]], dtype=mstype.float32)
        >>> GradNetWrtX(Net())(x, y)
        Tensor(shape=[2, 3], dtype=Float32,
        [[1.4100001 1.5999999 6.6      ]
         [1.4100001 1.5999999 6.6      ]])
        >>>
        >>> class GradNetWrtXY(nn.Cell):
        >>>     def __init__(self, net):
        >>>         super(GradNetWrtXY, self).__init__()
        >>>         self.net = net
        >>>         self.grad_op = GradOperation(get_all=True)
        >>>     def construct(self, x, y):
        >>>         gradient_function = self.grad_op(self.net)
        >>>         return gradient_function(x, y)
        >>>
        >>> x = Tensor([[0.8, 0.6, 0.2], [1.8, 1.3, 1.1]], dtype=mstype.float32)
        >>> y = Tensor([[0.11, 3.3, 1.1], [1.1, 0.2, 1.4], [1.1, 2.2, 0.3]], dtype=mstype.float32)
        >>> GradNetWrtXY(Net())(x, y)
        (Tensor(shape=[2, 3], dtype=Float32,
        [[4.5099998 2.7       3.6000001]
         [4.5099998 2.7       3.6000001]]), Tensor(shape=[3, 3], dtype=Float32,
        [[2.6       2.6       2.6      ]
         [1.9       1.9       1.9      ]
         [1.3000001 1.3000001 1.3000001]]))
        >>>
        >>> class GradNetWrtXYWithSensParam(nn.Cell):
        >>>     def __init__(self, net):
        >>>         super(GradNetWrtXYWithSensParam, self).__init__()
        >>>         self.net = net
        >>>         self.grad_op = GradOperation(get_all=True, sens_param=True)
        >>>         self.grad_wrt_output = Tensor([[0.1, 0.6, 0.2], [0.8, 1.3, 1.1]], dtype=mstype.float32)
        >>>     def construct(self, x, y):
        >>>         gradient_function = self.grad_op(self.net)
        >>>         return gradient_function(x, y, self.grad_wrt_output)
        >>>
        >>> x = Tensor([[0.8, 0.6, 0.2], [1.8, 1.3, 1.1]], dtype=mstype.float32)
        >>> y = Tensor([[0.11, 3.3, 1.1], [1.1, 0.2, 1.4], [1.1, 2.2, 0.3]], dtype=mstype.float32)
        >>> GradNetWrtXYWithSensParam(Net())(x, y)
        (Tensor(shape=[2, 3], dtype=Float32,
        [[2.211     0.51      1.4900001]
         [5.588     2.68      4.07     ]]), Tensor(shape=[3, 3], dtype=Float32,
        [[1.52       2.82       2.14      ]
         [1.1        2.05       1.55      ]
         [0.90000004 1.55       1.25      ]]))
        >>>
        >>> class GradNetWithWrtParams(nn.Cell):
        >>>     def __init__(self, net):
        >>>         super(GradNetWithWrtParams, self).__init__()
        >>>         self.net = net
        >>>         self.params = ParameterTuple(net.trainable_params())
        >>>         self.grad_op = GradOperation(get_by_list=True)
        >>>     def construct(self, x, y):
        >>>         gradient_function = self.grad_op(self.net, self.params)
        >>>         return gradient_function(x, y)
        >>>
        >>> x = Tensor([[0.8, 0.6, 0.2], [1.8, 1.3, 1.1]], dtype=mstype.float32)
        >>> y = Tensor([[0.11, 3.3, 1.1], [1.1, 0.2, 1.4], [1.1, 2.2, 0.3]], dtype=mstype.float32)
        >>> GradNetWithWrtParams(Net())(x, y)
        (Tensor(shape=[1], dtype=Float32, [21.536]),)
        >>>
        >>> class GradNetWrtInputsAndParams(nn.Cell):
        >>>     def __init__(self, net):
        >>>         super(GradNetWrtInputsAndParams, self).__init__()
        >>>         self.net = net
        >>>         self.params = ParameterTuple(net.trainable_params())
        >>>         self.grad_op = GradOperation(get_all=True, get_by_list=True)
        >>>     def construct(self, x, y):
        >>>         gradient_function = self.grad_op(self.net, self.params)
        >>>         return gradient_function(x, y)
        >>>
        >>> x = Tensor([[0.1, 0.6, 1.2], [0.5, 1.3, 0.1]], dtype=mstype.float32)
        >>> y = Tensor([[0.12, 2.3, 1.1], [1.3, 0.2, 2.4], [0.1, 2.2, 0.3]], dtype=mstype.float32)
        >>> GradNetWrtInputsAndParams(Net())(x, y)
        ((Tensor(shape=[2, 3], dtype=Float32,
        [[3.52 3.9  2.6 ]
         [3.52 3.9  2.6 ]]), Tensor(shape=[3, 3], dtype=Float32,
        [[0.6       0.6       0.6      ]
         [1.9       1.9       1.9      ]
         [1.3000001 1.3000001 1.3000001]])), (Tensor(shape=[1], dtype=Float32, [12.902]),))
    """

    def __init__(self, get_all=False, get_by_list=False, sens_param=False):
        self.get_all = get_all
        self.get_by_list = get_by_list
        self.sens_param = sens_param
        GradOperation_.__init__(self, 'grad', get_all, get_by_list, sens_param)
        self.grad_fn = None
        self.fn = None
        self.need_forward = False

    def _pynative_forward_run(self, args, kwargs, fn):
        """ Pynative forward run to build grad graph. """
        if self.sens_param:
            args = args[:-1]
        for arg in args:
            if not isinstance(arg, Tensor):
                raise TypeError("grad inputs should be tensor in pynative mode")
        if isinstance(fn, FunctionType):
            _pynative_exec.set_grad_flag(True)
            _pynative_exec.new_graph(fn, *args, **kwargs)
            output = fn(*args, **kwargs)
            _pynative_exec.end_graph(fn, output, *args, **kwargs)
        else:
            if fn.already_run and not fn.requires_grad:
                raise ValueError("obj must set_grad.")
            if not fn.already_run:
                self.need_forward = True
            if self.need_forward:
                fn.set_grad()
                fn(*args, **kwargs)
                fn.already_run = False

    def __call__(self, fn, weights=None):
        grad_ = GradOperation(self.get_all, self.get_by_list, self.sens_param)
        if self.grad_fn is None or self.fn != fn:
            if context.get_context("mode") == context.GRAPH_MODE:
                if self.get_by_list:
                    @ms_function(obj=fn)
                    def after_grad(*args):
                        return grad_(fn, weights)(*args)
                else:
                    @ms_function(obj=fn)
                    def after_grad(*args):
                        return grad_(fn)(*args)
            else:
                @_wrap_func
                def after_grad(*args, **kwargs):
                    self._pynative_forward_run(args, kwargs, fn)
                    _pynative_exec.grad(grad_, fn, weights, *args, **kwargs)
                    out = _pynative_exec(*args, **kwargs)
                    _pynative_exec.clear()
                    return out
            self.grad_fn = after_grad
            self.fn = fn
        return self.grad_fn


class MultitypeFuncGraph(MultitypeFuncGraph_):
    """
    Generate multiply graph.

    MultitypeFuncGraph is a class used to generate graphs for function with different type as input.

    Args:
        name (str): Operator name.

    Raises:
        ValueError: Cannot find matching fn for the given args.

    Examples:
        >>> # `add` is a metagraph object which will add two objects according to
        >>> # input type using ".register" decorator.
        >>> add = MultitypeFuncGraph('add')
    """

    def __init__(self, name):
        MultitypeFuncGraph_.__init__(self, name)
        self.entries = list()

    def __call__(self, *args):
        def unwrap(arg):
            if isinstance(arg, Parameter):
                return arg.data
            return arg
        types = tuple(map(lambda arg: mstype.get_py_obj_dtype(unwrap(arg)), args))
        for sigs, fn in self.entries:
            if len(sigs) != len(types):
                continue
            if any(not mstype.issubclass_(type_, sig) for sig, type_ in zip(sigs, types)):
                continue
            output = fn(*args)
            return output
        raise ValueError("Cannot find fn match given args.")

    def register(self, *type_names):
        """Register a function for the given type string."""
        def deco(fn):
            types = tuple(map(mstype.typing.str_to_type, type_names))
            self.register_fn(type_names, fn)
            self.entries.append((types, fn))
            return fn
        return deco


class HyperMap(HyperMap_):
    """
    Hypermap will apply the set operation on input sequences.

    Which will apply the operations of every elements of the sequence.

    Args:
        ops (Union[MultitypeFuncGraph, None]): `ops` is the operation to apply. If `ops` is `None`,
            the operations should be putted in the first input of the instance.

    Inputs:
        - **args** (Tuple[sequence]) - If `ops` is not `None`, all the inputs should be the same length sequences,
          and each row of the sequences. e.g. If args length is 2, and for `i` in length of each sequence
          `(args[0][i], args[1][i])` will be the input of the operation.

          If `ops` is not `None`, the first input is the operation, and the other is inputs.

    Outputs:
        sequence, the output will be same type and same length of sequence from input and the value of each element
        is the result of operation apply each row of element. e.g. `operation(args[0][i], args[1][i])`.
    """

    def __init__(self, ops=None):
        self.ops = ops
        if ops:
            HyperMap_.__init__(self, ops)
        else:
            HyperMap_.__init__(self)

    def __call__(self, *args):
        func = self.ops
        args_list = args
        hypermap = self
        if self.ops is None:
            func = args[0]
            args_list = args[1:]
            hypermap = partial(self, func)
        # is leaf
        if not isinstance(args_list[0], (tuple, list)):
            return func(*args_list)
        return tuple(map(hypermap, *args_list))


class Map(Map_):
    """
    Map will apply the set operation on input sequences.

    Which will apply the operations of every elements of the sequence.

    Args:
        ops (Union[MultitypeFuncGraph, None]): `ops` is the operation to apply. If `ops` is `None`,
            the operations should be putted in the first input of the instance.

    Inputs:
        - **args** (Tuple[sequence]) - If `ops` is not `None`, all the inputs should be the same length sequences,
          and each row of the sequences. e.g. If args length is 2, and for `i` in length of each sequence
          `(args[0][i], args[1][i])` will be the input of the operation.

          If `ops` is not `None`, the first input is the operation, and the other is inputs.

    Outputs:
        sequence, the output will be same type and same length of sequence from input and the value of each element
        is the result of operation apply each row of element. e.g. `operation(args[0][i], args[1][i])`.
    """

    def __init__(self, ops=None):
        self.ops = ops
        if ops:
            Map_.__init__(self, ops)
        else:
            Map_.__init__(self)

    def __call__(self, *args):
        func = self.ops
        args_list = args
        if self.ops is None:
            func = args[0]
            args_list = args[1:]
        return tuple(map(func, *args_list))


class _ListAppend(ListAppend_):
    """
    A metafuncgraph class that append one element to list.

    Args:
        name (str): The name of the metafuncgraph object.
    """
    def __init__(self, name):
        ListAppend_.__init__(self, name)

    def __call__(self, *args):
        pass


_append = _ListAppend("append")


class _Tail(Tail_):
    """
    A metafuncgraph class that generates tail elements of the tuple.

    Args:
        name (str): The name of the metafuncgraph object.
    """

    def __init__(self, name):
        Tail_.__init__(self, name)

    def __call__(self, *args):
        pass


tail = _Tail('tail')


class _ZipOperation(ZipOperation_):
    """Generates a tuple of zip iterations for inputs."""

    def __init__(self, name):
        ZipOperation_.__init__(self, name)

    def __call__(self, *args):
        pass


zip_operation = _ZipOperation('zip_operation')
"""`zip_operation` will generate a tuple of zip iterations of inputs."""


env_get = MultitypeFuncGraph("env_get")


@env_get.register("EnvType", "Tensor")
def _tensor_env_get(env, parameter):
    """Used to get env."""
    return F.env_getitem(env, F.ref_to_embed(parameter), F.zeros_like(parameter))
