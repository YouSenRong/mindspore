/**
 * Copyright 2020 Huawei Technologies Co., Ltd
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include "src/runtime/kernel/arm/int8/crop_int8.h"
#include <limits>
#include "nnacl/int8/crop_int8.h"
#include "include/errorcode.h"
#include "src/runtime/runtime_api.h"

using mindspore::kernel::KERNEL_ARCH::kCPU;
using mindspore::lite::RET_ERROR;
using mindspore::lite::RET_MEMORY_FAILED;
using mindspore::lite::RET_OK;

namespace mindspore::kernel {

int CropInt8CPUKernel::Init() {
  auto ret = CropBaseCPUKernel::Init();
  if (ret != RET_OK) {
    return ret;
  }
  auto *input_tensor = in_tensors_.at(kInputIndex);
  auto in_quant_args = input_tensor->GetQuantParams();
  crop_para_->quant_arg.in_args_.scale_ = in_quant_args.front().scale;
  crop_para_->quant_arg.in_args_.zp_ = in_quant_args.front().zeroPoint;

  auto *out_tensor = out_tensors_.at(kOutputIndex);
  auto out_quant_args = out_tensor->GetQuantParams();
  crop_para_->quant_arg.out_args_.scale_ = out_quant_args.front().scale;
  crop_para_->quant_arg.out_args_.zp_ = out_quant_args.front().zeroPoint;

  crop_para_->quant_arg.output_activation_max_ = std::numeric_limits<int8_t>::max();
  crop_para_->quant_arg.output_activation_min_ = std::numeric_limits<int8_t>::min();
  crop_para_->in_shape_ = reinterpret_cast<int *>(malloc(input_tensor->shape().size() * sizeof(int)));
  if (crop_para_->in_shape_ == nullptr) {
    MS_LOG(ERROR) << "malloc memory failed";
    return RET_MEMORY_FAILED;
  }
  crop_para_->out_shape_ = reinterpret_cast<int *>(malloc(out_tensor->shape().size() * sizeof(int)));
  if (crop_para_->out_shape_ == nullptr) {
    MS_LOG(ERROR) << "malloc memory failed";
    return RET_MEMORY_FAILED;
  }
  if (!InferShapeDone()) {
    return RET_OK;
  }
  return ReSize();
}

CropInt8CPUKernel::~CropInt8CPUKernel() {
  if (crop_para_->in_shape_ != nullptr) {
    free(const_cast<int *>(crop_para_->in_shape_));
    crop_para_->in_shape_ = nullptr;
  }

  if (crop_para_->out_shape_ != nullptr) {
    free(const_cast<int *>(crop_para_->out_shape_));
    crop_para_->out_shape_ = nullptr;
  }
}

int CropInt8CPUKernel::ReSize() {
  auto *input_tensor = in_tensors_.at(kInputIndex);
  auto input_shape = input_tensor->shape();
  size_t input_dim = input_shape.size();

  if (crop_para_->in_shape_ == nullptr) {
    MS_LOG(ERROR) << "in_shape_ is nullptr";
    return RET_ERROR;
  } else {
    memcpy(reinterpret_cast<void *>(const_cast<int *>(crop_para_->in_shape_)), input_shape.data(),
           sizeof(int) * input_dim);
  }

  auto *out_tensor = out_tensors_.at(kOutputIndex);
  auto output_shape = out_tensor->shape();
  size_t output_dim = output_shape.size();

  if (crop_para_->out_shape_ == nullptr) {
    MS_LOG(ERROR) << "out_shape_ is nullptr";
    return RET_ERROR;
  } else {
    memcpy(reinterpret_cast<void *>(const_cast<int *>(crop_para_->out_shape_)), output_shape.data(),
           sizeof(int) * output_dim);
  }
  MS_ASSERT(input_dim <= CROP_OFFSET_MAX_SIZE);
  crop_para_->input_dim_ = input_dim;
  PadOffset(input_dim, crop_para_);
  return RET_OK;
}

int CropInt8CPUKernel::Run() {
  auto ret = Prepare();
  if (ret != RET_OK) {
    MS_LOG(ERROR) << "Prepare fail!ret: " << ret;
    return ret;
  }
  ret = ParallelLaunch(this->context_->thread_pool_, CropInt8Run, this, thread_count_);
  return ret;
}

void PadOffset(int input_dim, CropParameter *crop_para) {
  auto axis = crop_para->axis_;
  auto offsets_size = crop_para->offset_size_;
  MS_ASSERT(axis <= input_dim);
  if (offsets_size > 1) {
    MS_ASSERT(axis + offsets_size == input_dim);
  }
  for (int i = 0; i < input_dim; i++) {
    int crop_offset = 0;
    if (i >= axis) {
      if (offsets_size == 1) {
        crop_offset = crop_para->offset_[0];
      } else if (offsets_size > 1) {
        crop_offset = crop_para->offset_[i - axis];
      }
    }
    crop_para->in_offset_[i] = crop_offset;
  }
}

int CropInt8Run(void *cdata, int task_id) {
  auto crop = reinterpret_cast<CropInt8CPUKernel *>(cdata);
  crop->DoExecute(task_id);
  return RET_OK;
}

int CropInt8CPUKernel::DoExecute(int task_id) {
  auto input_tensor = in_tensors_.at(kInputIndex);
  auto out_tensor = out_tensors_.at(kOutputIndex);
  int8_t *input_data = reinterpret_cast<int8_t *>(input_tensor->MutableData());
  int8_t *output_data = reinterpret_cast<int8_t *>(out_tensor->MutableData());
  Crop(input_data, output_data, task_id, crop_para_);
  return RET_OK;
}

}  // namespace mindspore::kernel
