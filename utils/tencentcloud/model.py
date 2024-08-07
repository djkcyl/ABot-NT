# Copyright (c) 2018 Tencent Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from dataclasses import dataclass
from urllib.parse import urlparse

from httpx._types import ProxiesTypes


@dataclass
class HttpProfile:
    endpoint: str
    protocol: str = "https"
    method: str = "POST"
    timeout: int = 60
    keep_alive: bool = False
    proxy: ProxiesTypes | None = None
    root_domain: str = "tencentcloudapi.com"

    def __post_init__(self) -> None:
        self.scheme = self.protocol

    @property
    def url(self) -> str:
        url = urlparse(self.endpoint)
        return f"https://{self.endpoint}" if not url.hostname else self.endpoint
