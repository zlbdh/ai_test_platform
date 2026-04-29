from agents.action_handlers import _click_agreement_checkbox_if_present


class FakeCheckbox:
    def __init__(self, checked=False):
        self.checked = checked
        self.click_calls = 0
        self.check_calls = 0

    @property
    def first(self):
        return self

    def is_checked(self, timeout=1000):
        return self.checked

    def scroll_into_view_if_needed(self, timeout=3000):
        return None

    def click(self, timeout=5000, force=True):
        self.click_calls += 1
        self.checked = True

    def check(self, timeout=5000, force=True):
        self.check_calls += 1
        self.checked = True


class FakeLabel:
    def __init__(self, checkbox, visible=True):
        self.checkbox = checkbox
        self.visible = visible
        self.click_calls = 0

    @property
    def first(self):
        return self

    def is_visible(self):
        return self.visible

    def scroll_into_view_if_needed(self, timeout=3000):
        return None

    def click(self, timeout=5000, force=True):
        self.click_calls += 1
        self.checkbox.checked = True

    def locator(self, selector):
        if selector in (".el-checkbox__input", "input[type='checkbox']"):
            return self.checkbox
        raise AssertionError(f"Unexpected selector: {selector}")


class FakeGroup:
    def __init__(self, labels):
        self.labels = labels

    def filter(self, has_text=None):
        return self

    def count(self):
        return len(self.labels)

    def nth(self, idx):
        return self.labels[idx]


class FakePage:
    def __init__(self, labels):
        self.group = FakeGroup(labels)

    def locator(self, selector):
        return self.group


def test_click_agreement_checkbox_checks_visible_checkbox():
    checkbox = FakeCheckbox(checked=False)
    page = FakePage([FakeLabel(checkbox)])

    result = _click_agreement_checkbox_if_present(page, "我已阅读并同意用户协议")

    assert result is True
    assert checkbox.checked is True


def test_click_agreement_checkbox_noops_when_already_checked():
    checkbox = FakeCheckbox(checked=True)
    page = FakePage([FakeLabel(checkbox)])

    result = _click_agreement_checkbox_if_present(page, "《用户协议》")

    assert result is True
    assert checkbox.click_calls == 0
    assert checkbox.check_calls == 0


def test_click_agreement_checkbox_ignores_unrelated_target():
    checkbox = FakeCheckbox(checked=False)
    page = FakePage([FakeLabel(checkbox)])

    result = _click_agreement_checkbox_if_present(page, "登录按钮")

    assert result is False
    assert checkbox.checked is False
